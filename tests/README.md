# Test Organization Documentation

## Audio-Formation Test Structure

### 📁 **tests/** Directory Organization

#### **Unit Tests**
- `test_arabic.py` - Arabic text processing and diacritics
- `test_chunking.py` - Text chunking algorithms
- `test_engines.py` - TTS engine interfaces
- `test_export.py` - Export functionality
- `test_export_m4b.py` - M4B export specifics
- `test_ingest.py` - File ingestion
- `test_mix_unit.py` - Audio mixing unit tests
- `test_mixer.py` - Audio mixing integration
- `test_multispeaker.py` - Multi-speaker processing
- `test_pipeline.py` - Pipeline state machine
- `test_processor.py` - Audio processing
- `test_project.py` - Project management
- `test_qc.py` - Quality control
- `test_qc_final.py` - Final quality control
- `test_validation.py` - Schema validation
- `test_xtts.py` - XTTS engine specifics
- `test_composer.py` - Audio composition
- `test_sfx.py` - Sound effects
- `test_security.py` - Security utilities
- `test_server.py` - FastAPI server endpoints

#### **CLI Tests**
- `test_cli_cast.py` - CLI casting commands
- `test_cli_compose.py` - CLI composition commands
- `test_cli_mix.py` - CLI mixing commands
- `test_cli_preview.py` - CLI preview commands

#### **E2E Tests** (NEW)
- `test_e2e_pipeline.py` - Complete CLI pipeline E2E tests
- `test_dashboard_api_e2e.py` - Dashboard API E2E tests

---

## 🔄 **Migration Summary**

### **Moved from Root Directory:**
- ✅ `dashboard_api_test.py` → `tests/test_dashboard_api_e2e.py`
- ✅ `e2e_runner.py` → `tests/test_e2e_pipeline.py`

### **Enhancements Made:**
1. **Proper pytest integration** - Converted to pytest test classes
2. **Fixtures and parametrization** - Better test organization
3. **Skip conditions** - Conditional test execution
4. **Error handling** - Improved test reliability
5. **Documentation** - Comprehensive test documentation

---

## 🧪 **Test Categories**

### **Unit Tests** (Fast, isolated tests)
```bash
pytest tests/ -k "not e2e and not dashboard"
```

### **Integration Tests** (Component interaction)
```bash
pytest tests/test_server.py
pytest tests/test_multispeaker.py
```

### **E2E Tests** (Full pipeline)
```bash
# CLI E2E tests (requires test_samples/)
pytest tests/test_e2e_pipeline.py -v

# Dashboard API E2E tests (requires running server)
pytest tests/test_dashboard_api_e2e.py -v
```

### **Engine-Specific Tests**
```bash
# Test specific engines
pytest tests/test_e2e_pipeline.py::TestE2EPipeline::test_engine_pipeline[edge]
pytest tests/test_e2e_pipeline.py::TestE2EPipeline::test_engine_pipeline[gtts]
pytest tests/test_e2e_pipeline.py::TestE2EPipeline::test_elevenlabs_pipeline
```

---

## 📋 **Test Requirements**

### **For CLI E2E Tests:**
- Test samples in `./test_samples/`
- All TTS engines installed
- CLI properly configured

### **For Dashboard API E2E Tests:**
- Dashboard server running on `localhost:4001`
- API keys configured in `.env`
- Test samples available

### **For Engine Tests:**
- Edge-TTS: `pip install edge-tts`
- gTTS: `pip install gtts`
- XTTS: `pip install TTS`
- ElevenLabs: `ELEVENLABS_API_KEY` environment variable

---

## 🎯 **Test Coverage Goals**

### **Current Coverage:**
- Unit Tests: ~65%
- Integration Tests: ~80%
- E2E Tests: ~90% (when engines available)

### **Target Coverage:**
- Unit Tests: 80%+
- Integration Tests: 90%+
- E2E Tests: 95%+

---

## 🚀 **Running Tests**

### **Quick Test Run:**
```bash
# Run all unit tests
pytest tests/ -x -v

# Run specific test categories
pytest tests/test_e2e_pipeline.py -v
pytest tests/test_dashboard_api_e2e.py -v
```

### **Full Test Suite:**
```bash
# Complete test suite (may take 30+ minutes)
pytest tests/ -v --tb=short
```

### **CI/CD Integration:**
```bash
# Fast CI run (unit + integration only)
pytest tests/ -k "not e2e" --tb=short

# Full CI run (includes E2E)
pytest tests/ --tb=short
```

---

## 📊 **Test Results**

### **Test Reports:**
- Unit tests: Console output + coverage
- E2E tests: Markdown logs in `E2E_TEST_RESULTS_*.md`
- Dashboard tests: API response validation

### **Coverage Reports:**
```bash
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html for detailed coverage
```

---

*Test Organization Documentation*
