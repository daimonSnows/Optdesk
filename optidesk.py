# --- bootstrap para garantir libs no Streamlit Cloud ---
import sys, subprocess

def _pip(pkg):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
    except Exception as e:
        print("Falha instalando", pkg, e)

# Garante plotly (às vezes o Cloud ignora o requirements)
try:
    import plotly.express as px  # noqa
except ModuleNotFoundError:
    _pip("plotly==5.23.0")
    import plotly.express as px  # noqa
# -------------------------------------------------------
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
from io import StringIO

st.set_page_config(page_title="OptiDesk — Tickets", layout="wide")
st.markdown("<style>html,body,[class*='css']{font-family:Inter,system-ui,Segoe UI,Roboto,Arial,sans-serif}</style>", unsafe_allow_html=True)

DB = "optidesk.db"
def conn(): return sqlite3.connect(DB, check_same_thread=False)
def init_db():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL, descricao TEXT,
            prioridade TEXT, status TEXT, grupo TEXT, responsavel TEXT,
            hora_abertura TEXT, hora_fechamento TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS comentarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER, autor TEXT, texto TEXT, datahora TEXT,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE)""")
def add_ticket(titulo, descricao, prioridade, status, grupo, responsavel, hora_abertura, hora_fechamento):
    with conn() as c:
        c.execute("INSERT INTO tickets (titulo,descricao,prioridade,status,grupo,responsavel,hora_abertura,hora_fechamento) VALUES (?,?,?,?,?,?,?,?)",
                  (titulo,descricao,prioridade,status,grupo,responsavel,hora_abertura,hora_fechamento))
def update_ticket(id_, **fields):
    if not fields: return
    keys = ", ".join([f"{k}=?" for k in fields]); vals = list(fields.values())+[id_]
    with conn() as c: c.execute(f"UPDATE tickets SET {keys} WHERE id=?", vals)
def delete_ticket(id_):
    with conn() as c: c.execute("DELETE FROM tickets WHERE id=?", (id_,))
def list_tickets(where="1=1", params=()):
    with conn() as c: return pd.read_sql_query(f"SELECT * FROM tickets WHERE {where} ORDER BY id DESC", c, params=params)
def add_comment(ticket_id, autor, texto, datahora=None):
    if not datahora: datahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    with conn() as c: c.execute("INSERT INTO comentarios (ticket_id,autor,texto,datahora) VALUES (?,?,?,?)",(ticket_id,autor,texto,datahora))
def list_comments(ticket_id):
    with conn() as c: return pd.read_sql_query("SELECT * FROM comentarios WHERE ticket_id=? ORDER BY id DESC", c, params=(ticket_id,))

def diff_minutes(a,b):
    if not a or not b: return None
    try:
        a=datetime.strptime(a,"%Y-%m-%d %H:%M"); b=datetime.strptime(b,"%Y-%m-%d %H:%M")
        m=int((b-a).total_seconds()//60); return m if m>=0 else None
    except: return None
def hhmm(m): 
    if m is None: return "-"
    return f"{m//60:02d}:{m%60:02d}"

init_db()

st.sidebar.title("🧭 OptiDesk")
page = st.sidebar.radio("Navegação", ["📊 Dashboard","📝 Novo Ticket","📂 Tickets","📄 Relatórios"], index=0)
st.sidebar.divider()

if page=="📊 Dashboard":
    st.title("📊 Dashboard")
    today=date.today(); start=today.replace(day=1)
    end=(start.replace(month=start.month%12+1, year=start.year+(start.month//12))-timedelta(days=1))
    df=list_tickets("date(hora_abertura)>=date(?) AND date(hora_abertura)<=date(?)", (str(start),str(end)))
    total=len(df)
    abertos=int((df["status"]=="Aberto").sum()) if not df.empty else 0
    resolvidos=int((df["status"]=="Resolvido").sum()) if not df.empty else 0
    tempos=[t for t in (diff_minutes(r["hora_abertura"], r["hora_fechamento"]) for _,r in df.iterrows()) if t is not None]
    tmedio=hhmm(sum(tempos)//len(tempos)) if tempos else "-"
    c1,c2,c3=st.columns(3); c1.metric("Tickets no mês", total); c2.metric("Resolvidos", resolvidos); c3.metric("Tempo médio", tmedio)
    if not df.empty:
        cA,cB=st.columns(2)
        with cA: st.plotly_chart(px.histogram(df, x="status", title="Por status"), use_container_width=True)
        with cB: st.plotly_chart(px.histogram(df, x="prioridade", title="Por prioridade"), use_container_width=True)
        df["dia"]=pd.to_datetime(df["hora_abertura"]).dt.date
        byday=df.groupby("dia", as_index=False)["id"].count().rename(columns={"id":"tickets"})
        st.plotly_chart(px.bar(byday, x="dia", y="tickets", title="Tickets por dia"), use_container_width=True)
    else:
        st.info("Sem tickets neste período. Crie o primeiro em **Novo Ticket**.")

elif page=="📝 Novo Ticket":
    st.title("📝 Novo Ticket")
    c1,c2=st.columns([2,1])
    with c1:
        titulo=st.text_input("Título")
        descricao=st.text_area("Descrição")
        grupo=st.selectbox("Grupo", ["TI - Protheus","Infraestrutura","Suporte Geral","Outros"])
        responsavel=st.text_input("Responsável", value="Ana Carolina")
    with c2:
        prioridade=st.selectbox("Prioridade", ["Baixa","Média","Alta","Urgente"])
        status=st.selectbox("Status", ["Aberto","Em andamento","Resolvido"], index=0)
        hora_abertura=st.text_input("Data/Hora de abertura (YYYY-MM-DD HH:MM)", datetime.now().strftime("%Y-%m-%d %H:%M"))
        hora_fechamento=st.text_input("Data/Hora de fechamento (opcional)", "")
    if st.button("💾 Salvar", use_container_width=True):
        add_ticket(titulo,descricao,prioridade,status,grupo,responsavel,hora_abertura,hora_fechamento)
        st.success("Ticket criado!")

elif page=="📂 Tickets":
    st.title("📂 Tickets")
    f1,f2,f3,f4=st.columns(4)
    fs=f1.selectbox("Status", ["Todos","Aberto","Em andamento","Resolvido"])
    fp=f2.selectbox("Prioridade", ["Todos","Baixa","Média","Alta","Urgente"])
    fr=f3.text_input("Responsável")
    fg=f4.selectbox("Grupo", ["Todos","TI - Protheus","Infraestrutura","Suporte Geral","Outros"])
    d1,d2=st.columns(2); di=d1.date_input("De", value=None); df_=d2.date_input("Até", value=None)
    busca=st.text_input("🔎 Busca (título/descrição)")

    where=["1=1"]; params=[]
    if fs!="Todos": where.append("status=?"); params.append(fs)
    if fp!="Todos": where.append("prioridade=?"); params.append(fp)
    if fr: where.append("responsavel LIKE ?"); params.append(f"%{fr}%")
    if fg!="Todos": where.append("grupo=?"); params.append(fg)
    if di: where.append("date(hora_abertura)>=date(?)"); params.append(str(di))
    if df_: where.append("date(hora_abertura)<=date(?)"); params.append(str(df_))
    if busca: where.append("(titulo LIKE ? OR descricao LIKE ?)"); params+= [f"%{busca}%", f"%{busca}%"]
    data=list_tickets(" AND ".join(where), tuple(params))

    if not data.empty:
        tempos=[diff_minutes(a,b) for a,b in zip(data["hora_abertura"], data["hora_fechamento"])]
        data["Tempo"]=[hhmm(t) if t is not None else "-" for t in tempos]
        view=data[["id","titulo","prioridade","status","responsavel","grupo","hora_abertura","hora_fechamento","Tempo"]]
        st.dataframe(view, use_container_width=True, hide_index=True)

        st.markdown("### ⚙️ Ações")
        a1,a2,a3,a4=st.columns(4)
        with a1:
            id_close=st.number_input("ID para fechar", min_value=1, step=1, value=int(view.iloc[0]["id"]))
            if st.button("✅ Fechar agora"):
                update_ticket(int(id_close), status="Resolvido", hora_fechamento=datetime.now().strftime("%Y-%m-%d %H:%M"))
                st.success("Ticket fechado.")
        with a2:
            id_edit=st.number_input("ID para editar", min_value=1, step=1, value=int(view.iloc[0]["id"]), key="editid")
            nt=st.text_input("Novo título", key="nt"); nd=st.text_area("Nova descrição", key="nd")
            np=st.selectbox("Nova prioridade", ["","Baixa","Média","Alta","Urgente"], key="np")
            ns=st.selectbox("Novo status", ["","Aberto","Em andamento","Resolvido"], key="ns")
            nr=st.text_input("Novo responsável", key="nr")
            ng=st.selectbox("Novo grupo", ["","TI - Protheus","Infraestrutura","Suporte Geral","Outros"], key="ng")
            if st.button("✏️ Salvar edição"):
                fields={}
                if nt: fields["titulo"]=nt
                if nd: fields["descricao"]=nd
                if np: fields["prioridade"]=np
                if ns: fields["status"]=ns
                if nr: fields["responsavel"]=nr
                if ng: fields["grupo"]=ng
                if fields: update_ticket(int(id_edit), **fields); st.success("Ticket atualizado.")
        with a3:
            id_del=st.number_input("ID para excluir", min_value=1, step=1, value=int(view.iloc[0]["id"]), key="delid")
            if st.button("🗑️ Excluir"):
                delete_ticket(int(id_del)); st.warning("Ticket excluído.")
        with a4:
            csv=view.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Exportar CSV", csv, "optidesk_tickets.csv", "text/csv")

        st.markdown("---")
        st.markdown("### 💬 Detalhes & Comentários")
        c1,c2=st.columns([1,3])
        with c1:
            id_view=st.number_input("ID do ticket", min_value=1, step=1, value=int(view.iloc[0]["id"]))
        with c2:
            t=data[data["id"]==id_view]
            if t.empty:
                st.info("Informe um ID listado acima.")
            else:
                row=t.iloc[0]
                st.markdown(f"**[{row['id']}] {row['titulo']}**  \\n"
                            f"Prioridade: **{row['prioridade']}** • Status: **{row['status']}**  \\n"
                            f"Abertura: **{row['hora_abertura']}** • Fechamento: **{row['hora_fechamento'] or '-'}** • Tempo: **{row['Tempo']}**  \\n"
                            f"Responsável: **{row['responsavel']}** • Grupo: **{row['grupo']}**")
                st.markdown("#### Comentários")
                cdf=list_comments(int(id_view))
                if cdf.empty: st.info("Sem comentários ainda.")
                else:
                    for _, r in cdf.iterrows():
                        st.markdown(f"<div class='comment'><small>{r['datahora']} — {r['autor']}</small><br>{r['texto']}</div>", unsafe_allow_html=True)
                with st.form("novo_comentario"):
                    autor=st.text_input("Autor", value=row["responsavel"] or "Ana Carolina")
                    texto=st.text_area("Comentário")
                    ok=st.form_submit_button("➕ Adicionar comentário")
                    if ok and texto.strip():
                        add_comment(int(id_view), autor, texto.strip())
                        st.success("Comentário adicionado. Atualize a página para ver na lista.")
    else:
        st.info("Nenhum ticket com esses filtros.")

elif page=="📄 Relatórios":
    st.title("📄 Relatórios")
    r1,r2=st.columns(2); di=r1.date_input("De:", value=None); df_=r2.date_input("Até:", value=None)
    where=["1=1"]; params=[]
    if di: where.append("date(hora_abertura)>=date(?)"); params.append(str(di))
    if df_: where.append("date(hora_abertura)<=date(?)"); params.append(str(df_))
    data=list_tickets(" AND ".join(where), tuple(params))
    if data.empty:
        st.info("Cadastre tickets para ver relatórios.")
    else:
        tempos=[t for t in (diff_minutes(a,b) for a,b in zip(data["hora_abertura"], data["hora_fechamento"])) if t is not None]
        tmedio=hhmm(sum(tempos)//len(tempos)) if tempos else "-"
        total=len(data); resolvidos=int((data["status"]=="Resolvido").sum())
        k1,k2,k3=st.columns(3); k1.metric("Total", total); k2.metric("Resolvidos", resolvidos); k3.metric("Tempo médio", tmedio)
        c1,c2=st.columns(2)
        with c1: st.plotly_chart(px.histogram(data, x="status", title="Por status"), use_container_width=True)
        with c2: st.plotly_chart(px.histogram(data, x="prioridade", title="Por prioridade"), use_container_width=True)
        from io import StringIO
        html=StringIO()
        html.write("""<!doctype html><html lang='pt-br'><head><meta charset='utf-8'><title>Relatório OptiDesk</title>
<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap' rel='stylesheet'>
<style>body{font-family:Inter,Arial,sans-serif;background:#0b1220;color:#e5e7eb;padding:24px}
h1{margin:0 0 8px;font-size:28px} small{color:#9ca3af}
table{width:100%;border-collapse:collapse;margin-top:12px}
th,td{border:1px solid #1f2937;padding:8px;font-size:12px} th{background:#111827}
.kpi{display:inline-block;margin-right:16px;background:#111827;border:1px solid #1f2937;padding:10px 14px;border-radius:10px}
.section{margin-top:18px}</style></head><body>""")
        html.write(f"<h1>Relatório OptiDesk</h1><small>Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M')}</small><br><br>")
        html.write(f"<div class='kpi'><b>Total:</b> {total}</div>")
        html.write(f"<div class='kpi'><b>Resolvidos:</b> {resolvidos}</div>")
        html.write(f"<div class='kpi'><b>Tempo médio:</b> {tmedio}</div>")
        html.write("<div class='section'><h3>Tabela</h3>")
        html.write(data[["id","titulo","prioridade","status","responsavel","grupo","hora_abertura","hora_fechamento"]].to_html(index=False))
        html.write("</div></body></html>")
        st.download_button("⬇️ Baixar HTML (imprimir PDF)", html.getvalue().encode("utf-8"), "relatorio_optidesk.html", "text/html")
