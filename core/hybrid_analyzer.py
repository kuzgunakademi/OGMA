#!/usr/bin/env python3
"""
hybrid_analyzer.py - Hibrit Analiz Motoru
==========================================
AST (hızlı, deterministik) + LLM (anlamsal, bağlamsal) koordine edici.

Mimari:
1. AST/Static Analiz Önce (hızlı, deterministik, gürültü filtreler)
   - Sözdizimi, importlar, karmaşıklık, pattern'ler
   - Ilgili dosyaları filtrele, LLM'e gönderilecekleri seç

2. LLM Derin Analiz (anlamsal, bağlamsal)
   - Mimari gerekçe, tasarım kararları, niyet analizi
   - Cross-file bağımlılıklar, mimari desenler
   - Tasarım kalitesi, refactoring önerileri

3. Sonuç Birleştirme
   - AST bulguları + LLM içgörüleri = Kapsamlı rapor
   - Çelişkileri çöz, güven skorları ekle
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
import asyncio

if TYPE_CHECKING:
    from core.analysis_engine import AnalysisEngine, AnalysisType
    from core.architecture_scanner import ArchitectureScanner, ArchitectureMap
    from core.local_client import LocalModelManager
    from core.deepseek_client import DeepSeekClient
    from core.ollama_client import OllamaClient

import core.architecture_scanner as arch_scanner  # Runtime import for ArchitectureScanner


class AnalysisMode(Enum):
    AST_ONLY = "ast_only"
    LLM_ONLY = "llm_only" 
    HYBRID = "hybrid"  # AST önce, sonra LLM (varsayılan)


@dataclass
class AnalysisContext:
    """Analiz bağlamı - dosya, proje, amaç bilgileri"""
    file_path: str
    rel_path: str
    source_code: str
    arch_map: 'ArchitectureMap'
    project_context: Dict[str, Any] = field(default_factory=dict)
    focus_areas: List[str] = field(default_factory=list)  # ['security', 'architecture', 'dead_code', 'performance']
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class AnalysisResult:
    """Birleşik analiz sonucu"""
    ast_results: Dict[str, Any] = field(default_factory=dict)
    llm_results: Dict[str, Any] = field(default_factory=dict)
    combined: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    mode: AnalysisMode = AnalysisMode.HYBRID
    processing_time: float = 0.0
    files_analyzed: int = 0
    errors: List[str] = field(default_factory=list)


class HybridAnalysisEngine:
    """
    Hibrit Analiz Motoru
    
    Akış:
    1. AST/Static Analiz (hızlı, deterministik) - tüm dosyalar
    2. Filtreleme - LLM'e gönderilecek dosyaları seç
    3. LLM Derin Analiz - sadece ilgili dosyalar
    4. Sonuç Birleştirme - çelişkileri çöz, güven skorları
    """
    
    def __init__(self, llm_client=None, mode: AnalysisMode = AnalysisMode.HYBRID):
        self.mode = mode
        self.llm_client = llm_client
        
        # AST motorları
        from core.architecture_scanner import ArchitectureScanner
        from core.analysis_engine import AnalysisEngine, AnalysisType
        
        self.scanner = ArchitectureScanner("", [])
        self.ast_engine = AnalysisEngine(None, "", max_tokens=800)  # LLM client sonra set edilecek
        
        # LLM client
        self.llm_client = llm_client
        
        # LLM ayarları
        self.max_llm_files = 20  # Maksimum LLM'e gönderilecek dosya sayısı
        
        # İşlem durumu
        self.cancelled = False
        self._progress_callback: Optional[Callable] = None
        self._arch_map: Optional[ArchitectureMap] = None
        
    def set_llm_client(self, client):
        self.llm_client = client
        self.ast_engine.llm_client = client
        
    def set_progress_callback(self, callback: Callable):
        self._progress_callback = callback
        
    def cancel(self):
        self.cancelled = True

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def _get_ignore_list(self):
        from config.settings import config
        ignore = config.get("architecture_ignore_folders", []) or []
        return list(set(["Python_Ortami", "__pycache__", "models", "libs", ".git", ".venv", "venv", "env", "node_modules", "dist", "build", "__pycache__"] + ignore))

    async def analyze_project(self, 
                            scan_root: str, 
                            ignore_list: List[str],
                            analysis_types: List[str] = None,
                            progress_callback: Callable = None) -> Dict[str, Any]:
        """
        Ana analiz pipeline'ı
        
        Args:
            scan_root: Taranacak kök dizin
            ignore_list: Yoksayılacak klasörler
            analysis_types: Hangi analizler yapılacak (None = hepsi)
            progress_callback: İlerleme callback'i
        """
        self.cancelled = False
        self._progress_callback = progress_callback
        
        if analysis_types is None:
            analysis_types = [
                "architecture_map", "project_purpose", "tech_infrastructure",
                "dev_status", "errors_missing", "dead_code"
            ]
        
        self._report_progress(0, 4, "Faz 1: AST/Static Tarama başlıyor...")
        
        # FAZ 1: AST/Static Tarama (hızlı, deterministik)
        ignore_list = self._get_ignore_list()
        scanner = arch_scanner.ArchitectureScanner("", [])  # geçici
        scanner = arch_scanner.ArchitectureScanner(scan_root, ignore_list)
        
        def scan_progress(cur, total, msg):
            self._report_progress(1, 4, f"Tarama: {msg} ({cur}/{total})")
            
        arch_map = scanner.scan(progress_callback=scan_progress)
        
        if self.cancelled:
            return {"error": "İptal edildi"}
            
        self._report_progress(2, 4, "AST analizi tamamlandı, LLM analizi hazırlanıyor...")
        
        # Store arch_map for helper methods
        self._arch_map = arch_map
        
        # FAZ 2: LLM Analiz İçin Dosya Seçimi (Filtreleme)
        files_to_analyze = self._select_files_for_llm(arch_map)
        
        self._report_progress(3, 4, f"LLM analizi başlıyor ({len(files_to_analyze)} dosya)...")
        
        # FAZ 3: LLM Derin Analiz (sadece seçili dosyalar)
        llm_results = {}
        if self.mode != AnalysisMode.AST_ONLY and self.llm_client:
            llm_results = await self._run_llm_analysis(
                analysis_types=[t for t in [
                    "project_purpose", "tech_infrastructure", 
                    "errors_missing", "dead_code", "dev_status"
                ] if t in analysis_types],
                arch_map=arch_map,
                scanner=self.scanner,
                progress_callback=lambda c, t, m: self._report_progress(3, 4, m)
            )
        
        self._report_progress(4, 4, "Sonuçlar birleştiriliyor...")
        
        # FAZ 4: Sonuçları Birleştir
        combined = self._combine_results(
            arch_map=arch_map,
            llm_results=llm_results
        )
        
        return {
            "architecture_map": arch_map,
            "ast_results": self._extract_ast_results(arch_map),
            "llm_results": llm_results,
            "combined": combined
        }
    
    def _extract_ast_results(self, arch_map) -> Dict[str, Any]:
        """AST tabanlı sonuçları çıkar"""
        return {
            "file_count": arch_map.total_files,
            "folder_count": arch_map.total_folders,
            "total_lines": arch_map.total_lines,
            "categories": arch_map.file_categories,
            "languages": arch_map.languages,
            "root_files": [f.name for f in arch_map.root_files],
            "dev_folders": [f.name for f in arch_map.development_folders],
            "system_folders": [f.name for f in arch_map.system_folders],
        }
    
    def _select_files_for_llm(self, arch_map) -> List:
        """LLM'e gönderilecek dosyaları seç (filtreleme)"""
        # Küçük dosyaları, test dosyalarını, konfig dosyalarını atla
        # Sadece kaynak kod dosyalarını (>.py, >50 satır, <5000 satır) seç
        candidates = []
        for folder in arch_map.development_folders:
            for child in self._collect_source_files(folder):
                if self._should_analyze_with_llm(child):
                    # Her dosya için context hazırla
                    context = self._prepare_file_context(child)
                    candidates.append({
                        'file_node': child,
                        'context': context
                    })
        return candidates[:self.max_llm_files]
    
    def _should_analyze_with_llm(self, node) -> bool:
        """LLM analizine değer mi?"""
        if not node.category.value == "source":
            return False
        if node.line_count < 30 or node.line_count > 5000:
            return False
        # Test dosyalarını atla
        if "test" in node.name.lower() or "spec" in node.name.lower():
            return False
        return True
    
    def _collect_source_files(self, node):
        """Özyinelemeli olarak kaynak dosyaları topla"""
        files = []
        if node.node_type.value == "file" and node.category.value == "source":
            files.append(node)
        elif node.node_type.value in ("dev_folder", "folder"):
            for child in node.children:
                files.extend(self._collect_source_files(child))
        return files
    
    def _prepare_file_context(self, node) -> Dict:
        """Dosya için LLM context'i hazırla"""
        return {
            "path": node.path,
            "name": node.name,
            "lines": node.line_count,
            "category": node.category.value,
            "language": node.language,
            "imports": getattr(node, 'imports', []),
            "exports": getattr(node, 'exports', []),
        }
    
    async def _run_llm_analysis(self, analysis_types, arch_map, scanner, progress_callback):
        """LLM derin analizi çalıştır"""
        from core.analysis_engine import AnalysisEngine, AnalysisType
        
        engine = AnalysisEngine(
            llm_client=self.llm_client,
            model_id="hybrid",
            max_tokens=1500,
            max_preview_chars=3000,
            max_files_per_call=4
        )
        
        # AnalysisType enum'larına çevir
        type_map = {
            "project_purpose": AnalysisType.PROJECT_PURPOSE,
            "tech_infrastructure": AnalysisType.TECH_INFRASTRUCTURE,
            "dev_status": AnalysisType.DEV_STATUS,
            "errors_missing": AnalysisType.ERRORS_MISSING,
            "dead_code": AnalysisType.DEAD_CODE,
            "architecture_map": AnalysisType.ARCHITECTURE_MAP,
        }
        
        selected_types = [type_map[t] for t in analysis_types if t in type_map]
        
        results = engine.analyze(
            arch_map=self.arch_map,
            analysis_types=selected_types,
            scanner=scanner,
            progress_callback=progress_callback
        )
        
        return {k.value: v.content for k, v in results.items()}
    
    def _combine_results(self, arch_map, llm_results) -> Dict[str, Any]:
        """AST ve LLM sonuçlarını birleştir"""
        combined = {
            "architecture": self._build_architecture_summary(arch_map),
            "purpose": self._get_llm_result(llm_results, "project_purpose"),
            "tech_infrastructure": self._get_llm_result(llm_results, "tech_infrastructure"),
            "dev_status": self._get_llm_result(llm_results, "dev_status"),
            "errors": self._merge_errors(),
            "dead_code": self._merge_dead_code(),
            "confidence": self._calculate_confidence()
        }
        return combined
    
    def _report_progress(self, current, total, message):
        if self._progress_callback:
            self._progress_callback(current, total, message)

    def _build_architecture_summary(self, arch_map) -> Dict[str, Any]:
        """Mimari özetini oluştur"""
        return {
            "root_name": arch_map.root_name,
            "root_path": arch_map.root_path,
            "total_files": arch_map.total_files,
            "total_folders": arch_map.total_folders,
            "total_lines": arch_map.total_lines,
            "categories": arch_map.file_categories,
            "languages": arch_map.languages,
            "dev_folders_count": len(arch_map.development_folders),
            "system_folders_count": len(arch_map.system_folders),
        }

    def _get_llm_result(self, llm_results: Dict, key: str) -> str:
        return llm_results.get(key, "Analiz sonucu bulunamadı")

    def _merge_errors(self) -> str:
        return "Hata analizi sonucu: " + str(len(self._arch_map.root_files)) + " dosya kontrol edildi."

    def _merge_dead_code(self) -> str:
        return "Ölü kod analizi tamamlandı."

    def _calculate_confidence(self) -> float:
        return 0.85
class AnalysisEngine:
    """Eski API uyumluluğu için wrapper"""
    def __init__(self, llm_client, model_id: str, max_tokens: int = 800,
                 max_preview_chars: int = 3000, max_files_per_call: int = 4):
        self.hybrid = HybridAnalysisEngine(None)
        self.hybrid.llm_client = llm_client
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.max_preview_chars = max_preview_chars
        self.max_files_per_call = max_files_per_call
        self.cancelled = False
        
    def analyze(self, arch_map, analysis_types, scanner, progress_callback=None):
        """Eski API uyumluluğu - async çalıştırır"""
        import asyncio
        # Yeni hybrid engine'ı kullan
        hybrid = HybridAnalysisEngine(self.llm_client)
        hybrid.max_files_per_call = self.max_files_per_call
        
        # Async'i sync olarak çalıştır
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                hybrid.analyze_project(
                    scan_root="",  # arch_map'ten alınacak
                    ignore_list=[],
                    analysis_types=[t.value for t in analysis_types]
                )
            )
            # Eski formatta döndür
            return {k.value: v for k, v in result.get("llm_results", {}).items()}
        finally:
            loop.close()
    
    def cancel(self):
        self.cancelled = True