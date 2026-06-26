from langchain_community.vectorstores import Chroma
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings

# 1. Load the exact same math model we used to save the data
embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

# 2. Connect to the existing memory folder
db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_function)

# 3. Define the question we want to ask
query = "What is the secret password for the servers?"
print(f"Searching memory for: '{query}'\n")

# 4. Search the database for the 1 closest mathematical match (k=1)
docs = db.similarity_search(query, k=1)

print("--- AI MEMORY RETRIEVED ---")
print(docs[0].page_content)