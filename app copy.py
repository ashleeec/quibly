import os
import uuid
import json
import sqlite3
from contextlib import closing
from typing import List, Dict

import pandas as pd
import streamlit as st
from openai import OpenAI

# -------------------------
# 1. CONFIG
# -------------------------
# Quick hackathon mode: **hard‑code** your key here. Replace the placeholder.
OPENAI_API_KEY = "[INSERT OPENAI API KEY HERE]"
client = OpenAI(api_key=OPENAI_API_KEY)

DB_PATH = "mvp.db"

# -------------------------
# 2. SQLITE LAYER
# -------------------------

def init_db() -> None:
    """Create tables if they don't already exist (idempotent)."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS assignments(
                id TEXT PRIMARY KEY,
                topic TEXT,
                goal TEXT,
                description TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions(
                id TEXT PRIMARY KEY,
                assignment_id TEXT,
                student_name TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages(
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # NEW: store latest assessment per student session
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments(
                session_id TEXT PRIMARY KEY,
                summary TEXT,
                score TEXT
            )
            """
        )
        conn.commit()


def fetch_one(sql: str, params: tuple = ()):  # helper
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()


def fetch_all(sql: str, params: tuple = ()):  # helper
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params: tuple = ()):  # helper
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()


init_db()

# -------------------------
# 3. OPENAI
# -------------------------


def tutor_reply(topic: str, goal: str, history: List[Dict[str, str]]) -> str:
    """Generate next Socratic tutor message."""
    system_prompt = (
        f"You are a teacher’s assistant. Your job is to have a discussion with the student to assess the student’s current understanding of {topic} using {goal} as a benchmark(s). "
        "You are forward thinking and believe the future of education to be driven by curiosity. Thus, you use the socratic and other effective and engaging learning methods backed by science, asking one question at a time and adjusting the level of difficulty based on the student’s last response. "
        "You may not give answers outright. However, you may prompt or nudge the student by using probing questions. "
        "In addition to just asking questions, you can have students design something, find errors in a short paragraph, and role play (especially for historical subjects). Use your creativity to find ways to assess the student and keep them engaged. "
        "Once you believe you have enough information to assess the student, say “Thank you for chatting today, you’re good to go!” and end the conversation."
    )
    messages = [{"role": "system", "content": system_prompt}] + history
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    return resp.choices[0].message.content


@st.cache_data(show_spinner=False)
def summarize_student(topic: str, goal: str, transcript: List[Dict[str, str]]):
    """Return JSON with 'summary' and qualitative 'score'."""
    system_prompt = """
You are an assessment assistant. Given the Socratic dialogue between the tutor and a student, produce a JSON object with keys 'summary' and 'score'.

• 'summary' should be an 80-word (or shorter) synthesis of the student's current understanding.
• 'score' must be one of the following EXACT strings: Unfamiliar, Rudimentary, Competent, Advanced, or Masterful.

Interpretation of levels:
Unfamiliar  – Student shows little to no grasp of core concepts, demonstrates major misconceptions, or is using this tool inappropriately. Student needs additional support.
Rudimentary – Student recognizes terms but has significant gaps or errors. Student fails to meet some learning objectives.
Competent   – Student meets the learning objectives with occasional mistakes that can be self‑corrected.
Advanced    – Student exceeds objectives; only minor nuances need polish.
Masterful   – Student demonstrates nuanced, thorough understanding and can extend concepts with ease.
"""
    user_blob = (
        f"Topic: {topic}\nObjectives: {goal}\nTranscript: {json.dumps(transcript, ensure_ascii=False)}"
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_blob},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)

def store_assessment(session_id:str, result:dict):
    execute("""INSERT INTO assessments(session_id,summary,score)
               VALUES(?,?,?)
               ON CONFLICT(session_id) DO UPDATE SET
                 summary=excluded.summary,
                 score=excluded.score""",
            (session_id,result["summary"],result["score"]))

def summarize_class(topic: str, goal: str, student_summaries: list[dict]) -> dict:
    system_prompt = (
        "You are an assessment assistant giving teachers overview of the level of understanding of the class. When you output your summary, structure feedback so teachers get a holistic overview paragraph of the class, then list common strengths and weaknesses among the class. Finally, talk about next steps on how the teacher should proceed with addressing these gaps in knowledge.\n"
        "Return **JSON only** with the keys exactly as follows:\n"
        "{\n"
        '  "overview": "<100-word synthesis>",\n'
        '  "strengths": item1, item2, ...,\n'
        '  "weaknesses": item1, item2, ...,\n'
        '  "next_steps": action1, action2, ...\n'
        "}\n"
        "Do not include student names in the text."
    )

    blob = json.dumps(student_summaries, ensure_ascii=False)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Topic: {topic}\nGoal: {goal}\nData: {blob}",
            },
        ],
        # 👇  forces valid JSON output
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)

# -------------------------
# 4. STREAMLIT UI
# -------------------------

st.set_page_config(page_title="quibly", page_icon="📚", layout="wide")
st.title("quibly")
role=st.sidebar.radio("I am a…",("Student","Teacher"))

# ---------- TEACHER VIEW ----------
if role=="Teacher":
    st.subheader("Create a new assignment")
    t_topic=st.text_input("Topic (e.g. Photosynthesis))")
    t_goal=st.text_area("Learning objectives (comma‑separated)")
    t_desc=st.text_area("Intro / instructions shown to students",height=100)

    if st.button("Generate & Share Code",disabled=not(t_topic and t_goal)):
        code=str(uuid.uuid4())[:8]
        execute("INSERT INTO assignments (id,topic,goal,description) VALUES (?,?,?,?)",
                (code,t_topic,t_goal,t_desc))
        st.success(f"Assignment code **{code}** generated. Share it!")

    st.divider()
    st.subheader("Dashboard")
    dash_code=st.text_input("Enter assignment code to review")

    if dash_code:
        sessions=fetch_all("SELECT id, student_name FROM sessions WHERE assignment_id=?",(dash_code,))
        if not sessions:
            st.info("No sessions yet or invalid code.")
        else:
            topic,goal=fetch_one("SELECT topic, goal FROM assignments WHERE id=?",(dash_code,))
            rows=[]
            for sid,sname in sessions:
                assessment=fetch_one("SELECT summary, score FROM assessments WHERE session_id=?",(sid,))
                if assessment is None:
                    msgs=fetch_all("SELECT role, content FROM messages WHERE session_id=?",(sid,))
                    chat=[{"role":r,"content":c} for r,c in msgs]
                    result=summarize_student(topic,goal,chat)
                    store_assessment(sid,result)
                    summary,score=result["summary"],result["score"]
                else:
                    summary,score=assessment
                rows.append({"Student":sname,"Summary":summary,"Score":score,"SID":sid})

            class_report=summarize_class(topic,goal,
                                         [{"name":r["Student"],"summary":r["Summary"],"score":r["Score"]} for r in rows])
            st.subheader("📊 Whole‑class snapshot")
            st.markdown(class_report['overview'])
            st.markdown(f"**Strengths:** {class_report['strengths']}")
            st.markdown(f"**Weaknesses:** {class_report['weaknesses']}")
            st.markdown(f"**Next steps:** {class_report['next_steps']}")

            def highlight(row):
                color="#ffe6e6" if row.Score in ("Unfamiliar","Rudimentary") else ""
                return [f"background-color: {color}"]*len(row)
            df=pd.DataFrame(rows).drop(columns=["SID"])
            st.dataframe(df.style.apply(highlight,axis=1),hide_index=True,use_container_width=True)

            st.subheader("🔍 Chat Transcripts")
            for r in rows:
                with st.expander(f"{r['Student']} – {r['Score']}"):
                    msgs=fetch_all("SELECT role, content FROM messages WHERE session_id=?",(r["SID"],))
                    for role_,content_ in msgs:
                        st.chat_message(role_).write(content_)

# ---------- STUDENT VIEW ----------
else:
    s_code=st.text_input("Assignment code")
    s_name=st.text_input("Your name")

    if st.button("Join",disabled=not(s_code and s_name)):
        record=fetch_one("SELECT topic, goal, description FROM assignments WHERE id=?",(s_code,))
        if record is None:
            st.error("Invalid code.")
        else:
            topic,goal,desc=record
            session_id=str(uuid.uuid4())
            execute("INSERT INTO sessions VALUES (?,?,?)",(session_id,s_code,s_name))
            st.session_state.update({
                "session_id":session_id,
                "assignment_code":s_code,
                "topic":topic,
                "goal":goal,
                "description":desc,
                "history":[],
            })
            st.info(desc or "No description provided by the teacher. Answer the tutor's question below!")

            opening=tutor_reply(topic,goal,[])
            execute("INSERT INTO messages(session_id, role, content) VALUES (?,?,?)",
                    (session_id,"assistant",opening))
            st.session_state["history"].append({"role":"assistant","content":opening})

    if "session_id" in st.session_state:
        chat_input=st.chat_input("Your reply…")
        if chat_input:
            sid=st.session_state["session_id"]
            execute("INSERT INTO messages(session_id, role, content) VALUES (?,?,?)",
                    (sid,"user",chat_input))
            st.session_state["history"].append({"role":"user","content":chat_input})

            reply=tutor_reply(st.session_state["topic"],st.session_state["goal"],st.session_state["history"])
            execute("INSERT INTO messages(session_id, role, content) VALUES (?,?,?)",
                    (sid,"assistant",reply))
            st.session_state["history"].append({"role":"assistant","content":reply})

        for m in st.session_state.get("history",[]):
            st.chat_message(m["role"]).write(m["content"])
