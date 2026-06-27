import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq

# 1. Load the environment variables from your secure vault (.env)
load_dotenv()

# Ensure the API key is present
if not os.getenv("GROQ_API_KEY"):
    raise ValueError("CRITICAL ERROR: GROQ_API_KEY not found in .env file!")

print("Vault unlocked successfully. Connecting to ChromaDB...")

# 2. Connect to your existing local Chroma vector database
persist_directory = "./chroma_db"
embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

db = Chroma(
    persist_directory=persist_directory, 
    embedding_function=embedding_function
)

# 3. Initialize the Groq AI Brain
# We use llama3-8b-8192 because it is incredibly fast and highly capable
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.2  # Low temperature keeps the answers grounded and factual
)

# 4. Define your testing query
query = "What is the secret password for the servers?"

print(f"\nSearching database for context regarding: '{query}'...")

# 5. Retrieve the most relevant chunk from your database
docs = db.similarity_search(query, k=1)

if not docs:
    print("No matching context found in the database.")
    context = "No relevant context found."
else:
    context = docs[0].page_content
    print(f"Retrieved Context: \"{context}\"")

# 6. Build the strict prompt template for the AI
system_prompt = (
    "You are a secure assistant. Answer the user's question using ONLY the provided context below. "
    "If the answer cannot be found in the context, say 'I do not know'.\n\n"
    f"Context:\n{context}\n\n"
    f"Question: {query}\n\n"
    "Answer:"
)

print("\nAI: Thinking...")

# 7. Fire the request over to Groq and stream the live answer
response = llm.invoke(system_prompt)

print("\n=================== AI RESPONSE ===================")
print(response.content)
print("===================================================\n")