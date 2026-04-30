from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import re
import psycopg2
from datetime import datetime
import pytz

app = FastAPI()

# 🔥 CONFIG
API_KEY = "key-fflikespanel"
BASE_URL = "https://api-freefire-psi.vercel.app"

DATABASE_URL = "postgresql://neondb_owner:npg_tqcgE5JarZ1F@ep-fragrant-recipe-acw0cl6r-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# 🔥 HEADERS NOVOS (GLOBAL)

# liberar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 🔧 FUNÇÕES BASE
# =========================

def gerar_cookie():
    try:
        session = requests.Session()

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://likesff.online/hpanel",
            "Origin": "https://likesff.online",
            "x-firebase-token": "qualquer_coisa"
        }

        session.post("https://likesff.online/api/session", headers=headers)

        cookie = session.cookies.get("__lff_s")

        return cookie
    except:
        return None

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def extract_token(data):
    if "eat=" in data:
        match = re.search(r"eat=([^&]+)", data)
        if match:
            return match.group(1)
    return data

def now_br():
    tz = pytz.timezone("America/Sao_Paulo")
    return datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")

# =========================
# 📦 CRIAR TABELAS
# =========================

def create_tables():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id SERIAL PRIMARY KEY,
            player_id TEXT,
            nickname TEXT,
            regiao TEXT,
            likes INTEGER,
            likes_depois INTEGER,
            novos_likes TEXT,
            falhas INTEGER,
            limite_site TEXT,
            data_hora TEXT
        )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS block (
        id SERIAL PRIMARY KEY,
        uid TEXT UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS agendamento (
            id SERIAL PRIMARY KEY,
            nickname TEXT,
            uid TEXT,
            token TEXT,
            dias INTEGER,
            likes_por_dia INTEGER,
            total_enviado INTEGER DEFAULT 0,
            total_erros INTEGER DEFAULT 0,
            erros_likes INTEGER DEFAULT 0,
            dias_executados INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ativo',
            ultima_execucao TEXT,
            data_criacao TEXT,
            inicial_likes INTEGER,
            atual_likes INTEGER
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

create_tables()

# =========================
# 🔥 ROTAS PRINCIPAIS
# =========================

@app.get("/set_bio")
def set_bio(token: str, bio: str):
    access_token = extract_token(token)

    r = requests.get("https://likesff.online/api/BIO", params={
        "access": access_token,
        "bio": bio
    })

    try:
        result = r.json()
    except:
        result = r.text

    return {
        "token_usado": access_token,
        "bio_enviada": bio,
        "resposta_api": result
    }

@app.get("/likes")
def enviar_likes(uid: str):

    conn = get_conn()
    cur = conn.cursor()

    # 🔴 VERIFICAR SE ESTÁ BLOQUEADO
    cur.execute("""
        SELECT uid FROM block
        WHERE uid=%s
        LIMIT 1
    """, (uid,))
    
    blocked = cur.fetchone()

    if blocked:
        cur.close()
        conn.close()
        return {
            "uid": uid,
            "status": "bloqueado",
            "mensagem": "UID está bloqueado no sistema"
        }

    # 🔴 VERIFICAR AGENDAMENTO
    cur.execute("""
        SELECT status FROM agendamento
        WHERE uid=%s
        ORDER BY id DESC
        LIMIT 1
    """, (uid,))

    result = cur.fetchone()

    if result and result[0] == "ativo":
        cur.close()
        conn.close()
        return {
            "uid": uid,
            "status": "bloqueado",
            "mensagem": "UID está em agendamento diário"
        }

    cur.close()
    conn.close()

    cookie = gerar_cookie()
    if not cookie:
        return {"erro": "falha ao gerar cookie"}
    
    session = requests.Session()

    # 🔥 ENVIO NORMAL
    r = session.get(
        "https://likesff.online/api/LIKE-SITE",
        params={
            "id": uid,
            "region": "BR"
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://likesff.online/hpanel",
            "Accept": "*/*"
        },
        cookies={
            "__lff_s": cookie
        }
    )

    try:
        data = r.json()
    except:
        data = r.text

    return {
        "uid": uid,
        "resultado": data
    }
# =========================
# 📊 HISTÓRICO
# =========================

@app.get("/historico_add")
def historico_add(
    player_id: str,
    nickname: str,
    regiao: str,
    likes: int,
    likes_depois: int,
    novos_likes: str,
    falhas: int,
    limite_site: str
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO historico 
        VALUES (DEFAULT,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        player_id, nickname, regiao,
        likes, likes_depois, novos_likes,
        falhas, limite_site, now_br()
    ))

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "salvo com sucesso"}


@app.get("/historico_listar")
def historico_listar():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM historico ORDER BY id DESC")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {"historico": rows}

# =========================
# 📅 AGENDAR LIKES
# =========================

@app.get("/agendar_likes")
def agendar_likes(uid: str, dias: int, key: str):

    if key != API_KEY:
        return {"erro": "key inválida"}

    if dias > 7:
        return {"erro": "Máximo 7 dias"}
    if dias < 1:
        return {"erro": "Mínimo 1 dia"}

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM agendamento
        WHERE uid=%s AND status='ativo'
    """, (uid,))
    
    if cur.fetchone():
        cur.close()
        conn.close()
        return {"erro": "UID já possui agendamento ativo"}

    cur.execute("""
        INSERT INTO agendamento
        (uid, dias, likes_por_dia, data_criacao)
        VALUES (%s,%s,220,%s)
    """, (uid, dias, now_br()))

    conn.commit()
    cur.close()
    conn.close()

    return {
        "status": "agendado",
        "total_likes": dias * 220
    }

# =========================
# 🚀 EXECUTAR AGENDAMENTOS
# =========================

def hoje_br():
    tz = pytz.timezone("America/Sao_Paulo")
    return datetime.now(tz).strftime("%d/%m/%Y")


@app.get("/enviar_agendamentos")
def enviar_agendamentos(key: str):

    if key != API_KEY:
        return {"erro": "key inválida"}

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, uid, dias, dias_executados, ultima_execucao
        FROM agendamento
        WHERE status='ativo'
    """)

    ags = cur.fetchall()
    resultados = []

    for ag in ags:
        ag_id, uid, dias, dias_exec, ultima_execucao = ag

        if ultima_execucao:
            try:
                data_ultima = ultima_execucao.split(" ")[0]
                if data_ultima == hoje_br():
                    resultados.append({
                        "uid": uid,
                        "status": "já enviado hoje"
                    })
                    continue
            except:
                pass

        if dias_exec >= dias:
            cur.execute("""
                UPDATE agendamento SET status='finalizado'
                WHERE id=%s
            """, (ag_id,))
            resultados.append({"uid": uid, "status": "finalizado"})
            continue

        tentativas = 0
        sucesso = False
        api_offline = False

        while tentativas < 2 and not sucesso:

            cookie = gerar_cookie()

            try:
                session = requests.Session()

                r = session.get(
                    "https://likesff.online/api/LIKE-SITE",
                    params={
                        "id": uid,
                        "region": "BR"
                    },
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://likesff.online/hpanel",
                        "Accept": "*/*"
                    },
                    cookies={
                        "__lff_s": cookie
                    }
                )

                data = r.json()
                res = data

                msg = res.get("message")
                res_text = res.get("res")

                if msg == "LIKES_SUCCESS":
                    sucesso = True

                    likes_add = res.get("likes_added", 0)
                    nickname = res.get("nickname")
                    likes_before = res.get("likes_before")
                    likes_end = res.get("likes_end")

                    esperado = 220
                    perdidos = esperado - likes_add
                    if perdidos < 0:
                        perdidos = 0

                    cur.execute("""
                        UPDATE agendamento
                        SET total_enviado = total_enviado + %s,
                            erros_likes = erros_likes + %s,
                            dias_executados = dias_executados + 1,
                            ultima_execucao = %s,
                            nickname = COALESCE(nickname, %s),
                            inicial_likes = COALESCE(inicial_likes, %s),
                            atual_likes = %s
                        WHERE id = %s
                    """, (likes_add, perdidos, now_br(), nickname, likes_before, likes_end, ag_id))

                    resultados.append({
                        "uid": uid,
                        "status": "sucesso",
                        "enviado": likes_add,
                        "perdidos": perdidos,
                        "resposta": res
                    })

                elif msg == "TOO_MANY_REQUESTS":
                    api_offline = True
                    resultados.append({
                        "uid": uid,
                        "status": "api_offline",
                        "resposta": res
                    })
                    break

                elif res_text == "Erro na Conexão com o Painel!!":
                    api_offline = True
                    resultados.append({
                        "uid": uid,
                        "status": "Api desligada ou em manutenção",
                        "resposta": res
                    })
                    break

                else:
                    tentativas += 1

            except:
                tentativas += 1

        if not sucesso and not api_offline:
            cur.execute("""
                UPDATE agendamento
                SET total_erros = total_erros + 1,
                    erros_likes = erros_likes + 220
                WHERE id = %s
            """, (ag_id,))

            resultados.append({
                "uid": uid,
                "status": "erro_total",
                "perdidos": 220,
                "resposta": res
            })

    conn.commit()
    cur.close()
    conn.close()

    return {
        "status": "execução finalizada",
        "resultados": resultados
    }

# =========================
# 📊 HISTÓRICO AGENDADO
# =========================

@app.get("/agendado_historico")
def agendado_historico():

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT uid, dias, dias_executados, total_enviado,
               total_erros, erros_likes, status,
               data_criacao, ultima_execucao, nickname, inicial_likes, atual_likes
        FROM agendamento
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    lista = []

    for r in rows:
        lista.append({
            "uid": r[0],
            "dias_total": r[1],
            "dias_executados": r[2],
            "dias_restantes": r[1] - r[2],
            "total_enviado": r[3],
            "total_erros": r[4],
            "erros_likes": r[5],
            "status": r[6],
            "data_criacao": r[7],
            "ultima_execucao": r[8],
            "nickname": r[9],
            "inicial_likes": r[10],
            "atual_likes": r[11]
        })

    return {"agendamentos": lista}
