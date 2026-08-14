#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from typing import Callable, List

from core.dependencies import Document, HAS_DOCX, HAS_PDF, HAS_PPTX, PdfReader, Presentation, pd
from external.ai_client import AIClient

class BatchProcessor:
    def __init__(self, ai_client: AIClient, log_callback: Callable):
        self.ai = ai_client
        self.log = log_callback

    def extract_text_from_file(self, file_path: str) -> List[str]:
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext in ['.txt','.md','.py','.html','.htm','.json','.xml','.css','.js']:
                with open(file_path,'r',encoding='utf-8') as f:
                    text = f.read()
                    return [text] if text.strip() else []
            elif ext in ['.xlsx','.xls']:
                if pd is None:
                    return [f"需要pandas读取Excel: {file_path}"]
                df = pd.read_excel(file_path, sheet_name=None, header=None)
                all_text = []
                for sheet_df in df.values():
                    sheet_text = sheet_df.astype(str).values.flatten()
                    sheet_text = ' '.join([t for t in sheet_text if t and t!='nan'])
                    if sheet_text:
                        all_text.append(sheet_text)
                return all_text
            elif ext == '.csv':
                if pd is None:
                    return [f"需要pandas读取CSV: {file_path}"]
                df = pd.read_csv(file_path, encoding='utf-8', header=None)
                text = df.astype(str).values.flatten()
                text = ' '.join([t for t in text if t and t!='nan'])
                return [text] if text.strip() else []
            elif ext == '.docx':
                if not HAS_DOCX:
                    return [f"需要python-docx: {file_path}"]
                doc = Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return ['\n'.join(paragraphs)] if paragraphs else []
            elif ext == '.pdf':
                if not HAS_PDF:
                    return [f"需要pypdf/PyPDF2: {file_path}"]
                reader = PdfReader(file_path)
                text = ''.join(page.extract_text() or '' for page in reader.pages)
                return [text.strip()] if text.strip() else []
            elif ext == '.pptx':
                if not HAS_PPTX:
                    return [f"需要python-pptx: {file_path}"]
                prs = Presentation(file_path)
                all_text = []
                for slide in prs.slides:
                    slide_text = [shape.text for shape in slide.shapes if hasattr(shape,"text") and shape.text.strip()]
                    if slide_text:
                        all_text.append('\n'.join(slide_text))
                return all_text
            else:
                return []
        except Exception as e:
            self.log(f"读取文件失败 {file_path}: {e}", "error")
            return []

    def process_folder(self, folder_path: str, mode: str, skip_search: bool, progress_callback: Callable, stop_flag: Callable, history_callback: Callable = None):
        supported_exts = {'.txt','.md','.py','.html','.htm','.json','.xml','.css','.js','.xlsx','.xls','.csv','.docx','.pdf','.pptx'}
        all_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if os.path.splitext(file)[1].lower() in supported_exts:
                    all_files.append(os.path.join(root, file))
        if not all_files:
            self.log("未找到支持的文件", "error")
            return
        total = len(all_files)
        self.log(f"找到 {total} 个文件，开始批量处理（模式: {mode}）", "system")
        for idx, file_path in enumerate(all_files):
            if stop_flag and stop_flag():
                self.log("批量处理被用户中断", "warning")
                break
            progress_callback(int(100*idx/total))
            self.log(f"\n处理文件 [{idx+1}/{total}]: {os.path.basename(file_path)}", "system")
            text_units = self.extract_text_from_file(file_path)
            if not text_units:
                self.log("  文件无有效内容或读取失败", "warning")
                continue
            for unit_idx, unit_text in enumerate(text_units):
                if len(unit_text.strip()) < 10:
                    continue
                if mode == "chat":
                    reply = self.ai.chat(unit_text)
                    self.log(f"  [{unit_idx+1}] AI 回应: {reply[:200]}...", "ai")
                    if history_callback:
                        history_callback("assistant", f"[批量处理文件 {os.path.basename(file_path)}] {reply}")
                else:
                    self.log(f"  [{unit_idx+1}] 晶体化处理（略）", "system")
                time.sleep(0.5)
        progress_callback(100)
        self.log("批量处理完成", "success")


