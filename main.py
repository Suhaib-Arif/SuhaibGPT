from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import shutil

from pymongo import MongoClient

import os

import warnings

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain import PromptTemplate
from langchain.chains.question_answering import load_qa_chain
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import Document
# from langchain.embeddings.google_palm import 

from transformers import pipeline
from nltk import pos_tag, word_tokenize

app = FastAPI()

client = MongoClient("mongodb://localhost:27017/")
db = client["chats"]
chats = db["chats"]
chats.create_index("session_id")


OPENAI_API_KEY = os.environ["open_ai"]
gemini_api_key = os.environ["gemini_key"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins. Replace with specific domains in production.
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)



class Talk(BaseModel):
    message: str

llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=gemini_api_key)

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

prompt_template = """You are a helpful chat bot, provide a response to the question based on the following context" \n\n
                    Context: \n {context}?\n
                    Question: \n {question} \n
                    Answer:
                  """

prompt = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)

warnings.filterwarnings("ignore")
important_tags = {'NN', 'NNP', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ', 'JJ', 'PRP'}


# Helper functions for MongoDB operations
def _create_new_session(session_id: str):
    """Create a new session in the MongoDB collection."""
    chats.insert_one({
        "session_id": session_id,
        "human_chat": [],
        "ai_chat": [],
        'summery': ""
    })

def _update_conversation(session_id: str, human_message: str, ai_message: str, generate_summery: bool):
    query = {"$push": {"human_chat": human_message, "ai_chat": ai_message}}
    print("Generate Summary: ",generate_summery)
    if generate_summery:
        summary = summarizer(human_message, max_length=30, min_length=5)[0]['summary_text']
        if not summary:
            summary = " ".join([item[0] for item in pos_tag(word_tokenize(human_message)) if item[1] in important_tags][:10])
        query.update({"$set": {"summery": summary}})

    print(query)
    result = chats.update_one(
        {"session_id": session_id},
        query
    )

def _get_session_memory(session_id, input_key=None):
    chat_history = chats.find_one({"session_id": session_id})
    memory = ConversationBufferMemory()
    
    for human, ai in zip(chat_history["human_chat"], chat_history["ai_chat"]):
        memory.chat_memory.add_user_message(human)
        memory.chat_memory.add_ai_message(ai)
    
    return memory

async def _get_memory(session_id):

    if session_id is None:
        generate_summery = True
        session_id = str(uuid4())
        memory = ConversationBufferMemory()
        print("Session Id",session_id)
        print("Memory", memory.buffer)
        _create_new_session(session_id)
    else:
        generate_summery = False
        memory =_get_session_memory(session_id)
    
    return memory , generate_summery ,session_id


@app.get("/get_chat_history/{session_id}")
async def get_chat_history(session_id):
    chat_history = chats.find_one({"session_id": session_id})
    history = []

    for human, ai in zip(chat_history["human_chat"], chat_history["ai_chat"]):
        chat = [
            {
            "text": human,
            "isBot": False,
            },
            {
            "text": ai,
            "isBot": True
            }
        ]
        history.extend(chat)
    
    return history




@app.get("/get_sessions")
async def get_session():
    return [{"session_id": item['session_id'], "summery":item["summery"]} for item in chats.find({})] 

@app.post("/talk")
async def make_request(request: Request, converse: Talk):

    session_id = request.headers.get("X-Session-ID")
    memory, generate_summery, session_id = await _get_memory(session_id)
    # print("Memory: ")

    conversation = ConversationChain(
        llm=llm, 
        memory=memory,
        verbose=True
    )

    human = converse.message
    print("Human: ",human)
    
    res = conversation.predict(input=human)

    print("Result: ",res)

    success = _update_conversation(session_id, human, res, generate_summery)

    print(success)

    return {"response": res, "session_id": session_id}

@app.post("/pdf_query/")
async def pdf_query(file: UploadFile = File(...), message: str =  Form(None), session_id:str =  Form(None),):

    print(file.filename)
    print(message)
    if message is None:
        raise("Error, message is empty")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file.content_type}")

    file_path = os.path.join("documents", file.filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # session_id = request.headers.get("X-Session-ID")
    # session_id = "036a17ca-d860-4cd7-b234-6aa27b133a15"
    print(session_id)
    memory, generate_summery, session_id = await _get_memory(session_id)
    memory.input_key = "question"
    # memory = ConversationBufferMemory(input_key="question", return_messages=True)


    pdf_loader = PyPDFLoader(file_path)
    pages = pdf_loader.load_and_split()

    os.unlink(file_path)

    documents = [Document(page_content=page.page_content) for page in pages]

    stuff_chain = load_qa_chain(llm, chain_type="stuff", prompt=prompt, memory=memory)

    print("Stuff Chain: ",stuff_chain)
    print("document and message", documents, message)

    stuff_answer = stuff_chain(
         {"input_documents": documents, "question": message}, return_only_outputs=True
    )

    if not stuff_answer["output_text"]:
        raise("AI did not generate answer")

    stuff_answer.update({"session_id": session_id})

    _update_conversation(session_id, message, stuff_answer["output_text"], generate_summery)

    return stuff_answer


