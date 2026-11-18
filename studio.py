"""Entry point for LangGraph Studio (dev only): pip install "langgraph-cli[inmem]", then langgraph dev."""
from langchain_ollama import ChatOllama

from db import connect_read_only
from graph import build_graph

graph = build_graph(ChatOllama(model="llama3.2", temperature=0, num_predict=300), connect_read_only())
