from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings

print("1. Loading document...")
loader = TextLoader("sample_doc.txt")
documents = loader.load()

print("2. Splitting text into chunks...")
text_splitter = CharacterTextSplitter(separator="\n", chunk_size=50, chunk_overlap=0)
chunks = text_splitter.split_documents(documents)

print("3. Downloading the embedding math model (this takes a minute on the first run)...")
embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

print("4. Converting text to numbers and saving to ChromaDB...")
db = Chroma.from_documents(chunks, embedding_function, persist_directory="./chroma_db")

print(f"Success! Embedded and saved {len(chunks)} chunks into the AI memory.")