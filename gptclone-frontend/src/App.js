import "./index.css";
// import gptLogo from "./assets/chatgpt.svg";
import gptImageLogo from "./assets/chatgptLogo.svg";
import addbtn from "./assets/add-30.png";
import sendbtn from "./assets/send.svg";
import { useState, useEffect } from "react";
import ReactMarkdown from 'react-markdown';
import gfm from 'remark-gfm';
import attachment from "./assets/paper-clip-svgrepo-com.svg";
import SuhaibGPT from "./assets/SuhaibGPT__2_-removebg-preview (1).png";
import user from "./assets/person.png";
import documentlogo from "./assets/document.png"

// import { Document } from 'react-pdf/dist/esm/entry.webpack';
// import 'react-pdf/dist/esm/Page/AnnotationLayer.css';


function App() {
  const [text, setText] = useState("");
  // const [numPages, setNumPages] = useState(null);
  // const [pageNumber, setPageNumber] = useState(1);
  // const [fileData, setFileData] = useState(null);
  const [fileKey, setFileKey] = useState(Date.now());
  const [messages, setMessages] = useState([
    {
      text: "I'm SuhaibGPT, an AI language model created by OpenAI. I'm here to help answer your questions, provide information, assist with tasks, or just have a conversation. What can I help you with today?",
      isBot: true,
    }
  ]);
  const [file, setFile] = useState(null);
  const [sessionid, setSessionID] = useState()
  const [sessions, setSessions] = useState([])


  const setCurrentSession = (sessid) => {
    fetch(`http://127.0.0.1:8000/get_chat_history/${sessid}`)
      .then((response) => response.json())
      .then(data => {setMessages(data);setSessionID(sessid)})
  }

  const handleSubmit = (event) => {
    event.preventDefault();

    const input = text;
    setMessages([
      ...messages,
      {text: input, isBot: false}
    ])
    setText("");


    if (sessionid == null || sessionid.trim() === ''){
        headers = {"Content-Type" : "application/json"}
      }else{
        headers = {"Content-Type" : "application/json", "X-Session-ID": sessionid}
      }


    if (file == null){
      ContactAI(headers, input);
    }else{
      sendPdf(headers, input);
    }

    setFile(null);
    setFileKey(Date.now());
  }

  const handleFileUpload = (e) => {
    setFile(e.target.files[0])
    // if (file){
    //   const fileURL = URL.createObjectURL(file);
    //   setFileData(fileURL);
    // }
    
  }

  const getSessions =() => {
    fetch("http://127.0.0.1:8000/get_sessions")
    .then((response) => response.json())
    .then(data => {setSessions(data)})
  }
  useEffect(() => {
    getSessions();
  }, [messages, sessionid])
  
  let headers = {}
  const ContactAI = async(headers, input) => {

    const response = await fetch("http://127.0.0.1:8000/talk", 
      {
          method:"POST",
          headers: headers,
          body: JSON.stringify({
            message: input
          }),
        }).then((response) => response.json());
        
    
        setMessages([
      ...messages,
      {text: input, isBot: false},
      {text: response.response, isBot: true}
    ]);
    setSessionID(response.session_id)
  };

  const sendPdf = async(headers, input) => {
    if (!file) {
      console.error("No file selected.");
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append("message", input);
    if (sessionid !== undefined){
      formData.append("session_id", sessionid)
    }
    const response = await fetch("http://127.0.0.1:8000/pdf_query", {
      method: "POST",
      body: formData
    }).then((response) => response.json());

    setMessages([
      ...messages,
      {text: input, isBot: false},
      {text: response.output_text , isBot: true}
    ]);

    console.log("Messages: ",messages);
    setSessionID(response.session_id);

    setFile(null);
    setFileKey(Date.now());
  }

  return (
    <div className="App">
      <div className="sidebar">
        <div className="uppersidebar">
          <div className="upperSideTop"><img src={SuhaibGPT} className="logo" alt="img" /></div>
          <button className="midBtn" onClick={() => {setSessionID(""); setMessages([]); getSessions();}}><img src={addbtn} alt="" className="addBtn"/>New Chat</button>

        </div>
        <div className="middleside">
        <div className="sessions">
          {sessions.map((session, i) =>
            <div className="session" onClick={() => {setCurrentSession(session.session_id)}}>
              {session.summery} 
            </div>          
          )}
        </div>
      </div>
      </div>
      <div className="main"> 
        <div className="chats">
          {messages.map((message, i) =>
              <div className={message.isBot? "chat bot": "chat"}>
                  <img src={message.isBot ? gptImageLogo : user} className="chatimg" alt="gpt"/><p><ReactMarkdown remarkPlugins={[gfm]} children={message.text}></ReactMarkdown></p>
              </div>
          )}

        </div>

        <div className="chatFooter">
        <form onSubmit={handleSubmit}>
        {file && (
          <div className="document">
            <div className="close-icon" onClick={()=>{setFile(null); setFileKey(Date.now());}} >&#x2716;</div>
            <div className="docimg">
              <img src={documentlogo} alt="img"/>
            </div>
            <div className="doctext">
              {file.name}
            </div>            
          </div>
        )}
        <div className="inp">
          <div className="file-input-container">
              <label htmlFor="file-input">
                <img src={attachment} alt="Upload icon" className="icon" />
              </label>
              <input type="file" accept="application/pdf" id="file-input" onChange={handleFileUpload} name="attachment" key={fileKey} style={{ display: 'none' }} />
          </div>
            <input type="text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Message SuhaibGPT" name="" id=""/><button type="submit" className="send"><img src={sendbtn} alt="sendbtn"></img></button>
          </div>
          </form>

        </div>
      </div>
    
    </div>
  );
}

export default App;
