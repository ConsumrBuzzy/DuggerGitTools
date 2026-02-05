# Security & Code Health Audit Report

**Project**: 
**Project Type**: python
**Timestamp**: 2026-02-05T09:00:27.442649
**Risk Score**: 6/100

---

🟢 **LOW RISK** - Project is relatively healthy

---

## 🧹 Dead Code (64)

_Potentially unused code that can be safely removed:_

- variable `__other` in [.venv\Lib\site-packages\annotated_types\__init__.py](file:///.venv\Lib\site-packages\annotated_types\__init__.py#L69):69
- variable `__other` in [.venv\Lib\site-packages\annotated_types\__init__.py](file:///.venv\Lib\site-packages\annotated_types\__init__.py#L74):74
- variable `__other` in [.venv\Lib\site-packages\annotated_types\__init__.py](file:///.venv\Lib\site-packages\annotated_types\__init__.py#L79):79
- variable `__other` in [.venv\Lib\site-packages\annotated_types\__init__.py](file:///.venv\Lib\site-packages\annotated_types\__init__.py#L84):84
- variable `__other` in [.venv\Lib\site-packages\annotated_types\__init__.py](file:///.venv\Lib\site-packages\annotated_types\__init__.py#L89):89
- variable `__other` in [.venv\Lib\site-packages\annotated_types\__init__.py](file:///.venv\Lib\site-packages\annotated_types\__init__.py#L94):94
- variable `__func` in [.venv\Lib\site-packages\click\core.py](file:///.venv\Lib\site-packages\click\core.py#L1633):1633
- variable `__func` in [.venv\Lib\site-packages\click\core.py](file:///.venv\Lib\site-packages\click\core.py#L1682):1682
- variable `resolutions` in [.venv\Lib\site-packages\pip\_internal\resolution\resolvelib\provider.py](file:///.venv\Lib\site-packages\pip\_internal\resolution\resolvelib\provider.py#L110):110
- variable `resolutions` in [.venv\Lib\site-packages\pip\_vendor\resolvelib\providers.py](file:///.venv\Lib\site-packages\pip\_vendor\resolvelib\providers.py#L15):15
- variable `__n` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L12):12
- variable `__limit` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L18):18
- variable `__hint` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L21):21
- variable `__offset` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L24):24
- variable `__whence` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L24):24
- variable `__size` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L33):33
- variable `__lines` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L39):39
- variable `__t` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L53):53
- variable `__traceback` in [.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py](file:///.venv\Lib\site-packages\pip\_vendor\rich\_null_file.py#L55):55
- variable `from_value` in [.venv\Lib\site-packages\pip\_vendor\six.py](file:///.venv\Lib\site-packages\pip\_vendor\six.py#L753):753
... and 44 more

---

## 📊 Project Metadata

- **Has Tests**: ✅
- **Has .gitignore**: ✅
- **Secrets Exposed**: 🟢 NO

## ⚠️ Scan Warnings

- pip-audit not installed (install: pip install pip-audit)

---

## 💡 Recommendations

3. Review and remove dead code to reduce maintenance burden