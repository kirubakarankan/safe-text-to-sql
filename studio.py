"""Entry point for LangGraph Studio (dev only): pip install "langgraph-cli[inmem]", then langgraph dev."""
from langchain_ollama import ChatOllama

from db import connect_read_only
from graph import build_graph

# shortcut: one connection shared by all runs; fine for one person in Studio, use a pool for real traffic.
conn = connect_read_only(check_same_thread=False)  # the server runs nodes in worker threads
graph = build_graph(ChatOllama(model="llama3.2", temperature=0, num_predict=300), conn)
