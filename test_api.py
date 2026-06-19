import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

os.environ["OPENAI_API_KEY"] 
os.environ["OPENAI_API_BASE"]

llm = ChatOpenAI(model="deepseek-v4-flash", temperature=0, max_retries=0, request_timeout=5)
try:
    print("Invoking...")
    res = llm.invoke([HumanMessage(content="Hi")])
    print(repr(res))
except Exception as e:
    print("Error:", repr(e))
