from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import shutil

from pymongo import MongoClient

import os

import warnings

from motor.motor_asyncio import AsyncIOMotorClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain import PromptTemplate
from langchain.chains.question_answering import load_qa_chain
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import ConversationChain, LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import Document
# from langchain.embeddings.google_palm import 

from transformers import pipeline
from nltk import pos_tag, word_tokenize

import redis
from redis.asyncio import Redis

import markdown
from bs4 import BeautifulSoup

async def get_redis():
    return redis.Redis(host='localhost', port=6379, db=0, encoding="utf-8", decode_responses=True)

app = FastAPI()

async def get_db():
    client = AsyncIOMotorClient("mongodb://localhost:27017/")
    db = clientdb = client["chats"]["chats"]
    return db

OPENAI_API_KEY = os.environ["openai_api"]
gemini_api_key = os.environ["Gemini_api"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins. Replace with specific domains in production.
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Summarization prompt template

# Create a summarization chain

warnings.filterwarnings("ignore")

class Talk(BaseModel):
    message: str

llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=gemini_api_key)


summarization_prompt = PromptTemplate(
    template="Identify the subject of the following conversation in less than 5 words:\n\nHuman: {Human}\nAI: {AI}\n\nSummary:",
    input_variables=["Human", "AI"]
)
# summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
summarization_chain = LLMChain(llm=llm, prompt=summarization_prompt)

prompt_template = """You are a helpful chat bot, provide a response to the question based on the following context" \n\n
                    Context: \n {context}?\n
                    Question: \n {question} \n
                    Answer:
                  """

prompt = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)

stuff_chain = load_qa_chain(llm, chain_type="stuff", prompt=prompt)



current_session_key = "Current_session"

conversation = ConversationChain(
        llm=llm, 
        verbose=True
    )

# Helper functions for MongoDB operations
async def _create_new_session(session_id: str, chats):
    """Create a new session in the MongoDB collection."""
    await chats.insert_one({
        "session_id": session_id,
        "human_chat": [],
        "ai_chat": [],
        'summery': ""
    })

def __get_summary(human_string, ai_string):
    return summarization_chain.run(Human=human_string, AI=ai_string)

def remove_markdown(md_text):
    # Convert markdown to HTML
    html = markdown.markdown(md_text)
    
    # Use BeautifulSoup to remove HTML tags
    soup = BeautifulSoup(html, "html.parser")
    
    return soup.get_text()


async def _update_conversation(session_id: str, human_message: str, ai_message: str, generate_summery: bool, chats):
    query = {"$push": {"human_chat": human_message, "ai_chat": ai_message}}
    print("Generate Summary: ",generate_summery)
    if generate_summery:
        summary = __get_summary(human_message, ai_message)
        summary = remove_markdown(summary)
        query.update({"$set": {"summery":summary}})

    print(query)
    await chats.update_one(
        {"session_id": session_id},
        query
    )

async def _get_session_memory(session_id, chats, input_key=None):
    chat_history = chats.find_one({"session_id": session_id})
    memory = ConversationBufferMemory()
    
    for human, ai in zip(chat_history["human_chat"], chat_history["ai_chat"]):
        memory.chat_memory.add_user_message(human)
        memory.chat_memory.add_ai_message(ai)
    
    return memory

async def _get_memory(session_id, chats):

    if session_id is None:
        generate_summery = True
        session_id = str(uuid4())
        memory = ConversationBufferMemory()
        print("Session Id",session_id)
        print("Memory", memory.buffer)
        await _create_new_session(session_id, chats)
    else:
        generate_summery = False
        memory = await _get_session_memory(session_id, chats)
    
    return memory , generate_summery ,session_id


@app.get("/get_chat_history/{session_id}")
async def get_chat_history(session_id, chats = Depends(get_db)):
    chat_history = await chats.find_one({"session_id": session_id})
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
async def get_session(chats = Depends(get_db)):
    sessions = await chats.find({}).to_list(length=None)
    return [{"session_id": item['session_id'], "summery":item["summery"]} for item in sessions] 

@app.post("/talk")
async def make_request(request: Request, converse: Talk, redis: Redis = Depends(get_redis), chats = Depends(get_db)):

    current_session = redis.get(current_session_key)
    session_id = request.headers.get("X-Session-ID")

    if session_id is None or (not conversation.memory.chat_memory.messages or current_session != session_id):
        print("True")
        memory, generate_summery, session_id = await _get_memory(session_id, chats)
        conversation.memory = memory
        redis.set(current_session_key, session_id)
    else: 
        generate_summery = False

    human = converse.message
    print("Human: ",human)
    
    res = conversation.predict(input=human)

    print("Result: ",res)

    await _update_conversation(session_id, human, res, generate_summery, chats)


    return {"response": res, "session_id": session_id}

@app.post("/pdf_query/")
async def pdf_query(file: UploadFile = File(...), message: str =  Form(None), session_id:str =  Form(None), redis: Redis = Depends(get_redis), chats = Depends(get_db)):

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file.content_type}")

    file_path = os.path.join("documents", file.filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    current_session = redis.get(current_session_key)
    if session_id is None or (not conversation.memory.chat_memory.messages or current_session != session_id):
        print("True")
        memory, generate_summery, session_id = await _get_memory(session_id, chats)
        conversation.memory = memory
        redis.set(current_session_key, session_id)
        memory.input_key = "question"
        stuff_chain.memory = memory
    else: 
        generate_summery = False
        
    # memory = ConversationBufferMemory(input_key="question", return_messages=True)


    pdf_loader = PyPDFLoader(file_path)
    pages = pdf_loader.load_and_split()

    os.unlink(file_path)

    documents = [Document(page_content=page.page_content) for page in pages]

    

    print("Stuff Chain: ",stuff_chain)
    print("document and message", documents, message)

    stuff_answer = stuff_chain(
         {"input_documents": documents, "question": message}, return_only_outputs=True
    )


    stuff_answer.update({"session_id": session_id})

    await _update_conversation(session_id, message, stuff_answer["output_text"], generate_summery, chats)

    return stuff_answer


# @app.post("/sample/{session_id}")
# async def make_request(converse: Talk, session_id: str, redis: Redis = Depends(get_redis)):
#     # session_id = request.headers.get("X-Session-ID")
#     if session_id == "None":
#         session_id = None
#     generate_summery = False

#     current_session = redis.get(current_session_key)


#     if session_id is None or (not conversation.memory.chat_memory.messages or current_session != session_id):
#         print("True")
#         memory, generate_summery, session_id = await _get_memory(session_id)
#         conversation.memory = memory
#         redis.set(current_session_key, session_id)

#     human = converse.message
#     print("Human: ",human)
    
#     res = conversation.predict(input=human)

#     print("Result: ",res)

#     success = _update_conversation(session_id, human, res, generate_summery)
 
#     print(success)

#     return {"response": res, "session_id": session_id}

