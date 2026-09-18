from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum
from datetime import datetime


class NodeType(Enum):
    FOLDER = "folder"
    FILE = "file"
    SYSTEM_FOLDER = "system_folder"
    DEV_FOLDER = "dev_folder"


class FileCategory(Enum):
    SOURCE = "source"
    CONFIG = "config"
    DOCUMENTATION = "docs"
    BUILD = "build"
    ASSET = "asset"
    DATA = "data"
    UNKNOWN = "unknown"


SOURCE_EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".java": "Java", ".cpp": "C++", ".c": "C", ".h": "Header",
    ".rs": "Rust", ".go": "Go", ".rb": "Ruby", ".php": "PHP",
    ".cs": "C#", ".swift": "Swift", ".kt": "Kotlin",
    ".sh": "Shell", ".bat": "Batch", ".ps1": "PowerShell",
    ".sql": "SQL", ".r": "R", ".scala": "Scala",
}

CONFIG_EXTENSIONS = {
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".ini": "INI", ".cfg": "Config",
    ".env": "Environment", ".xml": "XML", ".conf": "Config",
}

DOC_EXTENSIONS = {
    ".md": "Markdown", ".txt": "Text", ".rst": "reStructuredText",
    ".pdf": "PDF", ".doc": "Word",
}

ASSET_EXTENSIONS = {
    ".png": "Image", ".jpg": "Image", ".jpeg": "Image",
    ".gif": "Image", ".svg": "SVG", ".css": "CSS",
    ".html": "HTML", ".htm": "HTML",
}

DATA_EXTENSIONS = {
    ".csv": "CSV", ".db": "Database", ".sqlite": "SQLite",
    ".xlsx": "Excel", ".parquet": "Parquet",
}

BUILD_FILES = {
    "Makefile", "Dockerfile", "docker-compose.yml",
    "build.gradle", "pom.xml", "CMakeLists.txt",
    "setup.py", "setup.cfg", "pyproject.toml",
    "package.json", "Cargo.toml", "go.mod",
}

# Ikili agirlik/arsiv dosyalari: satir sayilmaz, onizleme verilmez.
SKIP_PREVIEW_EXTENSIONS = {
    ".gguf", ".ggml", ".bin", ".safetensors", ".onnx",
    ".pt", ".pth", ".ckpt", ".exe", ".dll", ".so",
    ".zip", ".7z", ".tar", ".gz",
}


@dataclass
class FileNode:
    name: str
    path: str
    absolute_path: str
    node_type: NodeType
    category: FileCategory = FileCategory.UNKNOWN
    language: str = ""
    size_bytes: int = 0
    line_count: int = 0
    purpose: str = ""
    children: List['FileNode'] = field(default_factory=list)
    child_count: int = 0
    total_lines: int = 0


@dataclass
class ArchitectureMap:
    root_path: str
    root_name: str
    scan_timestamp: str
    total_files: int = 0
    total_folders: int = 0
    total_lines: int = 0
    root_files: List[FileNode] = field(default_factory=list)
    development_folders: List[FileNode] = field(default_factory=list)
    system_folders: List[FileNode] = field(default_factory=list)
    ignored_folders: List[str] = field(default_factory=list)
    file_categories: Dict[str, int] = field(default_factory=dict)
    languages: Dict[str, int] = field(default_factory=dict)


class ArchitectureScanner:
    """Klasör yapısını tarar ve mimari harita oluşturur."""

    def __init__(self, scan_root: str, ignore_list: List[str]):
        self.scan_root = Path(scan_root).resolve()
        self.ignore_set = set(ignore_list)
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def scan(self, progress_callback=None) -> ArchitectureMap:
        """Tarama yap ve ArchitectureMap döndür."""
        self.cancelled = False

        arch_map = ArchitectureMap(
            root_path=str(self.scan_root),
            root_name=self.scan_root.name,
            scan_timestamp=datetime.now().isoformat(),
            ignored_folders=list(self.ignore_set),
        )

        if not self.scan_root.exists():
            return arch_map

        # Toplam dosya sayısını hesapla (progress için)
        total = self._count_total_items()
        current = [0]

        for item in sorted(self.scan_root.iterdir()):
            if self.cancelled:
                break

            if item.is_dir():
                if item.name in self.ignore_set or item.name.startswith("."):
                    # Sistem klasörü
                    sys_node = self._scan_folder(item, is_system=True)
                    arch_map.system_folders.append(sys_node)
                else:
                    # Geliştirme klasörü (kendisi de sayilir)
                    dev_node = self._scan_folder(item, is_system=False)
                    arch_map.development_folders.append(dev_node)
            elif item.is_file():
                if not item.name.startswith("."):
                    arch_map.root_files.append(self._scan_file(item))

            current[0] += 1
            if progress_callback and current[0] % 50 == 0:
                progress_callback(current[0], total, f"Taranıyor... ({current[0]}/{total})")

        self._aggregate_totals(arch_map)

        if progress_callback:
            progress_callback(total, total, "Tarama tamamlandı!")

        return arch_map

    def _aggregate_totals(self, arch_map: ArchitectureMap):
        """Tum agactan ozyinelemeli toplamlar (kok dosya + klasorler)."""
        arch_map.total_files = 0
        arch_map.total_folders = 0
        arch_map.total_lines = 0
        arch_map.file_categories = {}
        arch_map.languages = {}

        def visit_file(node: FileNode):
            arch_map.total_files += 1
            arch_map.total_lines += node.line_count
            cat = node.category.value
            arch_map.file_categories[cat] = arch_map.file_categories.get(cat, 0) + 1
            if node.language:
                arch_map.languages[node.language] = arch_map.languages.get(node.language, 0) + 1

        def visit_folder(node: FileNode):
            arch_map.total_folders += 1
            for child in node.children:
                if child.node_type == NodeType.FILE:
                    visit_file(child)
                elif child.node_type in (NodeType.FOLDER, NodeType.DEV_FOLDER):
                    visit_folder(child)
                # SYSTEM_FOLDER atlanir

        for f in arch_map.root_files:
            visit_file(f)
        for folder in arch_map.development_folders:
            visit_folder(folder)

    def _scan_folder(self, folder_path: Path, is_system: bool) -> FileNode:
        """Bir klasörü tara ve FileNode döndür."""
        node = FileNode(
            name=folder_path.name,
            path=str(folder_path.relative_to(self.scan_root)),
            absolute_path=str(folder_path),
            node_type=NodeType.SYSTEM_FOLDER if is_system else NodeType.DEV_FOLDER,
        )

        try:
            items = list(folder_path.iterdir())
        except (PermissionError, OSError):
            return node

        for item in sorted(items):
            if self.cancelled:
                break

            if item.is_dir():
                if item.name in self.ignore_set or item.name.startswith("."):
                    child = FileNode(
                        name=item.name,
                        path=str(item.relative_to(self.scan_root)),
                        absolute_path=str(item),
                        node_type=NodeType.SYSTEM_FOLDER,
                    )
                else:
                    child = self._scan_folder(item, is_system=False)
                    node.child_count += child.child_count
                    node.total_lines += child.total_lines
            elif item.is_file():
                if not item.name.startswith("."):
                    child = self._scan_file(item)
                    node.child_count += 1
                    node.total_lines += child.line_count
                else:
                    continue
            else:
                continue

            node.children.append(child)

        return node

    def _scan_file(self, file_path: Path) -> FileNode:
        """Bir dosyayı tara ve FileNode döndür."""
        node = FileNode(
            name=file_path.name,
            path=str(file_path.relative_to(self.scan_root)),
            absolute_path=str(file_path),
            node_type=NodeType.FILE,
            category=self._classify_file(file_path),
            language=self._get_language(file_path),
        )

        try:
            node.size_bytes = file_path.stat().st_size
        except (PermissionError, OSError):
            pass

        # Kaynak dosyalar için satır sayısı
        if node.category == FileCategory.SOURCE and node.size_bytes < 100_000:
            node.line_count = self._count_lines(file_path)

        return node

    def _classify_file(self, file_path: Path) -> FileCategory:
        """Dosya uzantısına göre kategori belirle."""
        ext = file_path.suffix.lower()
        name = file_path.name

        if name in BUILD_FILES:
            return FileCategory.BUILD
        if ext in SOURCE_EXTENSIONS:
            return FileCategory.SOURCE
        if ext in CONFIG_EXTENSIONS:
            return FileCategory.CONFIG
        if ext in DOC_EXTENSIONS:
            return FileCategory.DOCUMENTATION
        if ext in ASSET_EXTENSIONS:
            return FileCategory.ASSET
        if ext in DATA_EXTENSIONS:
            return FileCategory.DATA
        return FileCategory.UNKNOWN

    def _get_language(self, file_path: Path) -> str:
        """Dosya dilini döndür."""
        ext = file_path.suffix.lower()
        return SOURCE_EXTENSIONS.get(ext, "")

    def _count_lines(self, file_path: Path) -> int:
        """Dosya satır sayısını say (kaynak dosyalar için)."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except (PermissionError, OSError, UnicodeDecodeError):
            return 0

    def _count_total_items(self) -> int:
        """Toplam dosya+klasör sayısını say (progress için)."""
        count = 0
        try:
            for item in self.scan_root.rglob("*"):
                if item.name in self.ignore_set or item.name.startswith("."):
                    continue
                count += 1
                if count > 10000:  # Limit koy
                    break
        except (PermissionError, OSError):
            pass
        return max(count, 1)

    def get_file_content_preview(self, file_path: str, max_chars: int = 3000) -> str:
        """Dosya içeriğini oku (AI için kısaltılmış)."""
        if Path(file_path).suffix.lower() in SKIP_PREVIEW_EXTENSIONS:
            return "[Binary/agirlik dosyasi - onizleme atlandi]"
        try:
            full_path = self.scan_root / file_path
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(max_chars)
            if len(content) >= max_chars:
                content += "\n... [KISITLANDI]"
            return content
        except (PermissionError, OSError, UnicodeDecodeError):
            return "[Dosya okunamadi]"

    def get_tree_text(self, node: FileNode, indent: int = 0, max_depth: int = 3) -> str:
        """FileNode ağacını metin olarak döndür."""
        if indent > max_depth:
            return ""

        prefix = "│  " * (indent - 1) + "├── " if indent > 0 else ""
        lines = []

        if node.node_type == NodeType.SYSTEM_FOLDER:
            icon = "⚠️"
            label = f"{icon} {node.name} (Sistem - {node.child_count} dosya)"
        elif node.node_type == NodeType.DEV_FOLDER:
            icon = "🔧"
            label = f"{icon} {node.name} ({node.child_count} dosya, {node.total_lines} satır)"
        elif node.node_type == NodeType.FILE:
            cat_icons = {
                FileCategory.SOURCE: "📄", FileCategory.CONFIG: "⚙️",
                FileCategory.DOCUMENTATION: "📝", FileCategory.BUILD: "🔨",
                FileCategory.ASSET: "🎨", FileCategory.DATA: "📊",
            }
            icon = cat_icons.get(node.category, "📄")
            size_kb = node.size_bytes / 1024
            if node.line_count > 0:
                label = f"{icon} {node.name} ({node.line_count} satır, {size_kb:.1f}KB)"
            else:
                label = f"{icon} {node.name} ({size_kb:.1f}KB)"
        else:
            label = node.name

        lines.append(f"{prefix}{label}")

        if indent < max_depth:
            for child in node.children:
                if self.cancelled:
                    break
                child_text = self.get_tree_text(child, indent + 1, max_depth)
                if child_text:
                    lines.append(child_text)

        return "\n".join(lines)
