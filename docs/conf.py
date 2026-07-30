import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath('..'))

# 彻底 Mock 掉 fastapi 和所有相关子模块
mock_modules = [
    'tkinter', 'tkinter.ttk',
    'fastapi',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'fastapi.staticfiles',
    'fastapi.responses',
    'fastapi.background',
    'fastapi.datastructures',
    'fastapi.encoders',
    'fastapi.exceptions',
    'fastapi.params',
    'fastapi.types',
    'fastapi.utils',
    'uvicorn',
    'arxiv',
    'sentence_transformers',
    'chromadb',
    'pypdf',
    'docx',
    'pptx',
    'dotenv',
    'pandas',
    'bs4',
    'python_multipart',  # 如果还没安装，也 Mock 掉
]
for mod_name in mock_modules:
    sys.modules[mod_name] = MagicMock()

# 额外处理 fastapi 的 Form 等
fastapi_mock = MagicMock()
fastapi_mock.Form = MagicMock()
fastapi_mock.File = MagicMock()
fastapi_mock.UploadFile = MagicMock()
fastapi_mock.BackgroundTasks = MagicMock()
sys.modules['fastapi'] = fastapi_mock

project = '认知晶体树 API'
copyright = '2026, CrystalTree'
author = 'CrystalTree'
release = '3.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]

autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'private-members': False,
    'special-members': '__init__',
    'inherited-members': True,
}

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_rtype = True

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
exclude_patterns = []


# 1. 去掉模块前缀
add_module_names = False

# 2. 自动排除 BaseModel 继承的通用方法（适用于 Pydantic v2）
autodoc_default_options = {
    'exclude-members': (
        'model_config, model_fields, model_computed_fields, '
        'model_construct, model_copy, model_dump, model_dump_json, '
        'model_extra, model_fields_set, model_json_schema, '
        'model_parametrized_name, model_post_init, model_rebuild, '
        'model_validate, model_validate_json, model_validate_strings, '
        'parse_file, parse_obj, parse_raw, schema, schema_json, '
        'update_forward_refs, validate, '
        '__copy__, __deepcopy__, __get_pydantic_json_schema__, '
        '__iter__, __pretty__, __pydantic_init_subclass__, '
        '__pydantic_on_complete__, __repr_name__, __repr_recursion__, '
        '__rich_repr__, construct, copy, dict, from_orm, json'
    )
}

# 3. 如果不想手动列举，可以用更高级的过滤（跳过所有以 "model_" 开头的方法）
def skip_util_methods(app, what, name, obj, skip, options):
    if name.startswith('model_') or name in ('dict', 'json', 'copy', 'construct', 'parse_obj', 'validate'):
        return True
    return skip

def setup(app):
    app.connect('autodoc-skip-member', skip_util_methods)