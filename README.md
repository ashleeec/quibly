# Quibly 🧠💬  
**Adaptive, AI-powered exit tickets for deeper learning**  

Quibly replaces static classroom assessments with Socratic-style dialogues that adapt to each student’s understanding—giving teachers real-time insight into what students know, what they’re struggling with, and where to go next.

---

## ✨ Features

- **Socratic chat assistant** that probes student understanding with open-ended, adaptive questions  
- **Auto-generated mastery summaries** with qualitative ratings (Unfamiliar → Masterful)  
- **Teacher dashboard** with class-wide strengths, gaps, and next-step recommendations  
- **Flagging system** for inappropriate use and visibility into every student’s chat history  
- **Built-in safety**: no answer leakage, no accounts, no external data storage  

---

## 🏫 How It Works

1. **Teachers create an assignment**, set learning goals, and generate a join code.  
2. **Students chat with Quibly**, explaining their thinking and reasoning in a guided conversation.  
3. **Quibly summarizes** each chat into a brief understanding summary + competency level.  
4. **Teachers view a real-time dashboard** of insights, including flagged students and full transcript access.

---

## 🚀 Try It

Clone the repo and run locally with Streamlit:

```bash
git clone https://github.com/your-org/quibly.git
cd quibly
pip install -r requirements.txt
streamlit run app.py
```

Set your OpenAI API key in `.env` or via Streamlit secrets.

---

## 🔒 Safety First

Quibly is built for classroom use:
- No student accounts or identifiers  
- All conversations are reviewable by the teacher  
- AI never gives answers—only prompts deeper thinking  

---

## 📚 Tech Stack

- Python + Streamlit  
- SQLite for local session storage  
- OpenAI GPT-4o API for adaptive dialogue + assessment  

---

## 🛣️ Roadmap

- Essay-writing mode  
- Google Classroom & Canvas integrations  
- Rubric-aligned scoring + multilingual support

---

## 🧠 Built With a Vision

Quibly is grounded in curiosity, student-led learning, and the belief that AI should help students **explain, not guess**—and help teachers **see, not assume**.
