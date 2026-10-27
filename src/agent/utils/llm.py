from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

# Using Groq's fast and free Llama model
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.2, 
    streaming=True
)