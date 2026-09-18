# Devkit Model-Free Analysis - Development Plan
# =============================================
# Created: 2025-09-14
# Status: IN PROGRESS
# =============================================

## 📋 MASTER PLAN - Model-Free Analysis Enhancements

### 📊 CURRENT STATE
- All core modules compile and run
- AST parsing, symbol extraction, fingerprinting working
- Import graph, cycles, subsystem matrix working
- Quality scoring, techdebt, impact analysis working
- CLI and GUI both functional

### 🔴 PHASE 1: QUICK WINS - quality.py extensions (Week 1)
**Target: 5 analyses in 1 week**

| Task | Function | File | Status | Priority |
|------|----------|------|--------|----------|
| 1.1 | Unreachable code detection | quality.py | 🔴 TODO | HIGH |
| 1.2 | Unused variable detection (AST) | quality.py | ☐ TODO | HIGH |
| 1.3 | Type hint coverage % | quality.py | ☐ TODO | HIGH |
| 1.4 | Security pattern scanner | quality.py | ☐ TODO | HIGH |
| 1.5 | Cyclomatic complexity per function | quality.py | ☐ TODO | HIGH |
| 1.6 | Unreachable code after return/raise | quality.py | ☐ TODO | HIGH |
| 1.7 | Unused variable detection (AST-based) | quality.py | ☐ TODO | HIGH |

### 🟡 PHASE 2: NEW MODULES - Week 2

| Module | Purpose | Days | Status |
|--------|---------|------|--------|
| `arch_compliance.py` | Layer rules, naming conventions, architectural rules | 2 days | ☐ TODO |
| `api_breaking.py` | Breaking change detection (API surface diff) | 2 days | ☐ TODO |
| `security_scan.py` | Security patterns (eval, shell, pickle, SQL, secrets) | 1 day | ⏳ TODO |
| `dep_freshness.py` | Dependency freshness check | 1 day | ⏳ TODO |
| `license_check.py` | License compliance (SPDX) | 1 day | ⏳ TODO |
| `arch_compliance.py` | Layer rules, naming conventions | 2 days | ☐ TODO |
| `api_breaking.py` | API breaking change detection | 2 days | ☐ TODO |
| `security_scan.py` | Security patterns (eval, shell, pickle, SQL, secrets) | 1 day | ⏳ TODO |
| `dep_freshness.py` | Dependency version freshness | 1 day | ⏳ TODO |

### PHASE 3: INTEGRATION & EXTENSION

| Task | Module | Status |
|------|--------|--------|
| Cross-file dead code (call graph) | techdebt.py | ☐ TODO |
| Security patterns in quality | quality.py | 🔄 IN PROGRESS |
| Type hint coverage % | quality.py | ☐ TODO |
| Cyclomatic complexity per function | quality.py | ☐ TODO |
| Unreachable code detection | quality.py | ☐ TODO |
| Unused variable detection | quality.py | ☐ TODO |

### INTEGRATION POINTS
- [ ] Add to `cmd_techdebt` command
- [ ] Add to `cmd_quality` command  
- [ ] Add to `cmd_check` command
- [ ] Update `scan.py` to collect new data
- [ ] Update `techdebt.py` with cross-file dead code
- [ ] Update `quality.py` with new analyses
- [ ] Update `cmd_report` for new outputs
- [ ] Update `cmd_check` for new checks

---

## 📋 DETAILED IMPLEMENTATION SPECS

### 1. UNREACHABLE CODE DETECTION
```python
def detect_unreachable_code(tree) -> List[Issue]:
    """Detect code after return/raise/return in functions"""
    # Walk AST, find statements after return/raise/return in same block
```

### 2. UNUSED VARIABLE DETECTION (AST)
```python
def detect_unused_variables(tree) -> List[UnusedVar]:
    # Track assignments vs usage in same scope
```

### 3. TYPE HINT COVERAGE
```python
def type_hint_coverage(tree) -> Tuple[float, List[MissingHint]]
```

### 4. SECURITY PATTERNS
```python
SECURITY_PATTERNS = {
    "eval_exec": r"\b(eval|exec)\s*\(",
    "shell_injection": r"subprocess\.(run|Popen|call).*shell\s*=\s*True",
    "pickle_load": r"pickle\.(load|loads)\(",
    "yaml_unsafe_load": r"yaml\.load\((?!.*Loader=)",
    "sql_injection": r"execute\s*\(\s*[\"'].*%.*\)",
    "path_traversal": r"\.\./",
    "hardcoded_secret": r"(password|secret|token|key)\s*=\s*[\"']",
}
```

### 4. CYCLOMATIC COMPLEXITY
```python
def cyclomatic_complexity(node) -> int:
    """McCabe complexity: 1 + decision points"""
```

### 5. UNREACHABLE CODE
```python
def detect_unreachable_code(tree) -> List[Issue]:
    # Code after return/raise/return in same block
```

---

## IMPLEMENTATION ORDER

### DAY 1-2: quality.py extensions
- [ ] 1.1 Unreachable code detection
- [ ] 1.2 Unused variable detection (AST)
- [ ] 1.3 Type hint coverage %
- [ ] 1.4 Security pattern scanner
- [ ] 1.5 Cyclomatic complexity per function
- [ ] 1.6 Unreachable code after return/raise

### Day 3-4: New Modules
- [ ] `engine/security_scan.py` - Security patterns
- [ ] `engine/arch_compliance.py` - Layer rules, naming
- [ ] `engine/api_breaking.py` - Breaking change detection
- [ ] `engine/dep_freshness.py` - Dependency freshness
- [ ] `engine/license_check.py` - License compliance (SPDX)

### INTEGRATION
- [ ] Add to `cmd_techdebt`
- [ ] Add to `cmd_quality`
- [ ] Add to `cmd_check`
- [ ] Update `scan.py` to collect new data
- [ ] Update `techdebt.py` with cross-file dead code
- [ ] Update `quality.py` with new analyses
- [ ] Update `cmd_report` for new outputs
- [ ] Update `cmd_check` for new checks

---

## TESTING CHECKLIST
- [ ] py_compile all modified files
- [ ] Run on Ogma project (H:\Ogma)
- [ ] Run on devkit itself
- [ ] CLI: `devkit quality`, `devkit check`, `devkit techdebt`
- [ ] GUI: quality tab, techdebt tab
- [ ] Compare with previous outputs

---

## NOTES
- All analyses MUST be model-free (AST/static only)
- No external dependencies beyond stdlib
- Output must be JSON-serializable
- Each analysis: < 100ms per file
- Configurable via config.json
- Respect ignore_dirs