认知晶体树 API 文档
====================================

.. toctree::
   :maxdepth: 2
   :caption: 内容导航

配置与数据模型 (Config & Data)
-------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: Config, Layer, Crystal, Hole, Conflict, TaskCard, HealthCheckResult, CognitiveFingerprint, FingerprintExtractionResult, LayerContribution, AuditReport, VerifiableClaim, M3MADBenchResult, TwinProfile, PromptTemplate, DebateRole, RoleViewpoint, RoundDynamics, FinalOutputSchema
   :undoc-members:
   :show-inheritance:
   :no-index:

存储与数据库 (Storage & DB)
-------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: FileIO, DBManager, HealthChecker, NetworkManager, SearchService
   :undoc-members:
   :show-inheritance:
   :no-index:

外部抓取与集成 (External Fetch & Integration)
-----------------------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: ExternalFetcher
   :undoc-members:
   :show-inheritance:
   :no-index:

核心引擎与元层 (Core Engine & Meta)
-----------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: CrystalEngine, MetaLayer, ForceExplorer, LayerAuditService, RUMADController, AlarmMonitor
   :undoc-members:
   :show-inheritance:
   :no-index:

便宜门与向量检索 (Cheap Gate & Vector)
---------------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: CheapGate, VectorStore
   :undoc-members:
   :show-inheritance:
   :no-index:

AI 客户端与自我进化 (AI Client & Evolution)
--------------------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: AIClient, PromptTemplateManager, GödelAgent, FingerprintExtractor
   :undoc-members:
   :show-inheritance:
   :no-index:

辩论引擎与输出编排 (Debate & Output)
-------------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: DebateEngine, OutputOrchestrator, SynapseStore, compute_dashboard_stats
   :undoc-members:
   :show-inheritance:
   :no-index:

可验证主张与沙盒 (Verification & Sandbox)
------------------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: ClaimExtractor, SVRMADValidator, SandboxExecutor, M3MADBench, Day12Integration
   :undoc-members:
   :show-inheritance:
   :no-index:

替身与沉思 (Twin & Contemplative)
----------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: ContemplativeEngine, TwinWorkbench
   :undoc-members:
   :show-inheritance:
   :no-index:

反诈安全模块 (Anti-Fraud Security)
-----------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: AIPersonaDetector, StarlinkFingerprintDB, CrossLingualAuditor
   :undoc-members:
   :show-inheritance:
   :no-index:

计划与批处理 (Planning & Batch)
--------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: DailyPlanner, BatchProcessor, BaselineRunner, MetaSearchEngine
   :undoc-members:
   :show-inheritance:
   :no-index:

GUI 应用 (Tkinter App)
------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: CrystalTreeApp
   :undoc-members:
   :show-inheritance:
   :no-index:

Web API 数据契约 (Pydantic Models)
-----------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: AssetPatchRequest, BackendLoginRequest, BatchRequest, ChatRequest, CommitRequest, CrystalRequest, DailyPlanRequest, DeepReasonRequest, PendingConfirmRequest, SearchRequest, SessionCreate, SessionRename, SkillValidateRequest
   :undoc-members:
   :show-inheritance:
   :no-index:

内部任务辅助函数 (Internal Helpers)
-----------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: _job, _set_job, _log_job, _run_job
   :undoc-members:
   :show-inheritance:
   :no-index:

入口与全局函数 (Entry & Globals)
---------------------------------
.. automodule:: crystal_tree_all_in_one_day
   :members: apply_v3_patches, verify_day0_startup_assertions, verify_day1, generate_session_title_from_content, register_day12_api, main
   :undoc-members:
   :show-inheritance:
   :no-index: