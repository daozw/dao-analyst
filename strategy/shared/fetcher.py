"""共享数据源 — 所有策略共用"""
import json, urllib.request, ssl
ssl._create_default_https_context = ssl._create_unverified_context
from pipeline.fetcher import fetch, fetch_market
from pipeline.signals import analyze
