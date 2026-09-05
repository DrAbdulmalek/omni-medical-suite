# src/integrations/calibre_manager.py
"""Safe wrapper around the Calibre calibredb CLI."""
from __future__ import annotations
import json,re,subprocess
from pathlib import Path
from typing import Dict,List,Optional,Sequence
SAFE_TEXT_RE=re.compile(r"^[\w\u0600-\u06FF\s\-.,()]+$")
class CalibreError(RuntimeError): pass
class CalibreManager:
    def __init__(self,library_path:str|Path,calibredb_executable:str="calibredb",timeout:int=120)->None:
        self.library_path=Path(library_path).expanduser().resolve(); self.calibredb=calibredb_executable; self.timeout=timeout
        if not self.library_path.is_dir(): raise FileNotFoundError(f"Calibre library path does not exist: {self.library_path}")
    def _run(self,args:Sequence[str])->str:
        try: p=subprocess.run([str(self.calibredb),*args],check=True,capture_output=True,text=True,timeout=self.timeout)
        except subprocess.CalledProcessError as e: raise CalibreError(f"calibredb failed: {e.stderr.strip() or e.stdout.strip()}") from e
        except FileNotFoundError as e: raise CalibreError("calibredb executable not found. Install Calibre first.") from e
        except subprocess.TimeoutExpired as e: raise CalibreError("calibredb timed out") from e
        return p.stdout
    def is_available(self)->bool:
        try: self._run(["--version"]); return True
        except CalibreError: return False
    def _search_ids(self,query:str)->List[int]:
        if not query: return []
        out=self._run(["search","--library-path",str(self.library_path),query])
        return [int(line.strip()) for line in out.splitlines() if line.strip().isdigit()]
    def list_books(self,ids:Optional[List[int]]=None)->List[Dict]:
        args=["list","--library-path",str(self.library_path),"--for-machine","--fields","id,title,authors,tags"]
        if ids: args.extend(["--ids",",".join(str(i) for i in ids)])
        try: data=json.loads(self._run(args))
        except json.JSONDecodeError: return []
        return data if isinstance(data,list) else []
    def search_by_specialty(self,specialty:str)->List[Dict]:
        specialty=specialty.strip()
        if not specialty or not SAFE_TEXT_RE.fullmatch(specialty): raise ValueError("Specialty contains unsafe characters")
        ids=self._search_ids(f'tags:"specialty:{specialty}"')
        return self.list_books(ids) if ids else []
    def add_book(self,file_path:str|Path,title:Optional[str]=None,authors:Optional[str]=None,tags:Optional[str]=None)->str:
        path=Path(file_path).expanduser().resolve()
        if not path.is_file(): raise FileNotFoundError(f"File does not exist: {path}")
        args=["add","-1","--library-path",str(self.library_path)]
        for flag,value,label in [("--title",title,"Title"),("--authors",authors,"Authors"),("--tags",tags,"Tags")]:
            if value:
                if not SAFE_TEXT_RE.fullmatch(value): raise ValueError(f"{label} contains unsafe characters")
                args.extend([flag,value])
        return self._run([*args,str(path)])
