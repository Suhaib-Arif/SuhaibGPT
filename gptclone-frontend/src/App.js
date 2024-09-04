import "./index.css";
import gptLogo from "./assets/chatgpt.svg";
import gptImageLogo from "./assets/chatgptLogo.svg";
import addbtn from "./assets/add-30.png"
import sendbtn from "./assets/send.svg"
import userLogo from "./assets/user-icon.png"
import { useState, useEffect } from "react";
import ReactMarkdown from 'react-markdown'
import gfm from 'remark-gfm'
import attachment from "./assets/paper-clip-svgrepo-com.svg"

function App() {
  const [text, setText] = useState("");
  const [messages, setMessages] = useState([
    {
      text: "I'm ChatGPT, an AI language model created by OpenAI. I'm here to help answer your questions, provide information, assist with tasks, or just have a conversation. What can I help you with today?",
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
      setFile(null);
    }

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


  }


  return (
    <div className="App">
      <div className="sidebar">
        <div className="uppersidebar">
          <div className="upperSideTop"><img src={gptLogo} className="logo" alt="img" /><span className="brand">ChatGPT</span></div>
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
              <div className={message.isBot? "chat bot": "chat"} style={{textAlign: "left"}}>
                  <img src={message.isBot ? gptImageLogo : userLogo} className="chatimg" alt="gpt"/><p><ReactMarkdown remarkPlugins={[gfm]} children={message.text}></ReactMarkdown></p>
              </div>
          )}

        </div>

        <div className="chatFooter">
          <form onSubmit={handleSubmit}>
          <div className="inp">
          <div className="file-input-container">
              <label htmlFor="file-input">
                <img src={attachment} alt="Upload icon" className="icon" />
              </label>
              <input type="file" accept="application/pdf" id="file-input" onChange={(e) => {setFile(e.target.files[0])}} name="attachment" style={{ display: 'none' }} />
          </div>
            <input type="text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Message Chatgpt" name="" id=""/><button type="submit" className="send"><img src={sendbtn} alt="sendbtn"></img></button>
          </div>
          <p>ChatGPT may produce incorrent results sometimes.</p>
          </form>

        </div>
      </div>
    
    </div>
  );
}

export default App;
