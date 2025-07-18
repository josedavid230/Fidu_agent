import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- LÓGICA DEL AGENTE RAG ---

# 1. Definición de constantes
DOCUMENTS_PATH = "documents"
FAISS_INDEX_PATH = "faiss_index"

# Crear la carpeta de documentos si no existe para evitar errores
os.makedirs(DOCUMENTS_PATH, exist_ok=True)

# 2. Carga de la API Key de OpenAI desde el entorno
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("La variable de entorno OPENAI_API_KEY no está configurada.")

# 3. Inicialización del modelo de embeddings
embeddings = OpenAIEmbeddings(openai_api_key=api_key)

# 4. Creación y Carga del Vector Store (FAISS)
db = None
try:
    if os.path.exists(FAISS_INDEX_PATH):
        print(f"Cargando índice FAISS existente desde '{FAISS_INDEX_PATH}'...")
        db = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        print("Índice cargado exitosamente.")
    else:
        print(f"No se encontró un índice. Creando uno nuevo desde los documentos en '{DOCUMENTS_PATH}'...")
        loader = DirectoryLoader(DOCUMENTS_PATH, glob="**/*", show_progress=True, use_multithreading=True)
        docs = loader.load()

        if not docs:
            print(f"ADVERTENCIA: No se encontraron documentos en '{DOCUMENTS_PATH}'. El agente responderá sin contexto de archivos.")
        else:
            print(f"Se cargaron {len(docs)} documento(s). Dividiendo en fragmentos...")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(docs)
            
            print(f"Creando índice FAISS con {len(splits)} fragmentos. Esto puede tardar un momento...")
            db = FAISS.from_documents(splits, embeddings)
            db.save_local(FAISS_INDEX_PATH)
            print(f"Índice FAISS creado y guardado en '{FAISS_INDEX_PATH}'.")

except Exception as e:
    print(f"Error durante la inicialización del Vector Store: {e}")
    # db se mantiene como None, el endpoint manejará este caso.

# 5. Creación de la Cadena de QA (RAG Chain)
rag_chain = None
if db:
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 4})

    # Plantilla de Prompt Personalizada
    template = """
    Eres FidupreviBOT, un asesor comercial experto de Fiduprevisora. Tu misión es ser excepcionalmente útil, proactivo y fluido en tu comunicación, manteniendo siempre un tono formal pero cercano.

    **Contexto Relevante:**
    {context}

    **Pregunta del Cliente:**
    {question}

    **== Directrices de Comunicación ==**

    1.  **Respuesta Basada en Contexto:** Tu respuesta DEBE basarse estrictamente en el "Contexto Relevante" proporcionado. No inventes información. Si el contexto incluye URLs, no te limites a mostrarlas; extrae y presenta la información relevante de esas fuentes como si fuera tu propio conocimiento. El objetivo es que tú respondas la pregunta, no que envíes al usuario a otro sitio.

    2.  **Formato Fluido:** Estructura tus respuestas usando párrafos para que sean fáciles de leer y entender. Evita los bloques de texto largos y monótonos.

    3.  **Técnica del Buen Negociante (Si la Respuesta NO está en el Contexto):**
        *   **Nunca digas "no sé"** o "no tengo información". Es una frase prohibida.
        *   En su lugar, reconoce amablemente la consulta del cliente y, de manera fluida, haz una transición hacia los temas sobre los que SÍ tienes dominio según el contexto.
        *   **Sé proactivo:** Analiza el contexto disponible y ofrece alternativas o temas relacionados que podrían ser de interés para el cliente. Por ejemplo, podrías decir: "Entiendo tu interés en [tema de la pregunta]. Si bien no tengo los detalles específicos sobre eso en este momento, puedo ofrecerte información completa sobre [tema A del contexto] o [tema B del contexto]. ¿Te gustaría que profundicemos en alguno de ellos?".
        *   **El objetivo es mantener la conversación activa y útil**, guiando al cliente hacia el conocimiento que posees. Muestra siempre una actitud resolutiva y de búsqueda de soluciones.

    **Respuesta:**
    """
    prompt = ChatPromptTemplate.from_template(template)

    # Inicialización del LLM
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0, openai_api_key=api_key, max_tokens=350)

    # Creación de la cadena con LCEL
    rag_chain = (
        RunnableParallel({
            "context": retriever,
            "question": RunnablePassthrough()
        })
        | prompt
        | llm
        | StrOutputParser()
    )
    print("Cadena RAG creada exitosamente.")
else:
    print("ADVERTENCIA: El Vector Store (db) no está disponible. La cadena RAG no se pudo crear.")


class QuestionRequest(BaseModel):
    question: str

@app.get("/")
def read_root():
    return {"status": "ok"}

@app.post("/ask")
async def ask_question(request: QuestionRequest):
    if not rag_chain:
        return {"answer": "Lo siento, el agente de IA no está disponible en este momento. Asegúrate de que haya documentos en la carpeta 'documents' y de que la clave de API de OpenAI sea correcta."}

    try:
        print(f"Recibida pregunta: '{request.question}'")
        answer = rag_chain.invoke(request.question)
        print(f"Respuesta generada: '{answer}'")
        return {"answer": answer}
    except Exception as e:
        print(f"Error al procesar la pregunta: {e}")
        return {"answer": "Lo siento, ocurrió un error al procesar tu pregunta. Por favor, intenta de nuevo."}
