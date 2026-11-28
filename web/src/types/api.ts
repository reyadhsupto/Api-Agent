// Hand-written response contracts for the FastAPI backend.
//
// The routes return plain dictionaries, so OpenAPI has no response schema for
// them (see api.generated.ts for the request models it does describe). These
// interfaces name the payloads the UI reads, and tests/test_api_contract.py
// asserts that the critical routes keep emitting those fields. Index signatures
// keep unknown future fields legal without pretending to know them.

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS' | 'TRACE';

/** One editable key/value row, as stored by the backend. */
export interface ValueRow {
  enabled: boolean;
  key: string;
  value: string;
  description?: string;
}

/** Request shape sent through the backend proxy. */
export interface ApiRequest {
  method: HttpMethod;
  url: string;
  headers: Record<string, string>;
  query_params: Record<string, unknown>;
  body?: string | Record<string, unknown> | unknown[] | null;
  timeout_seconds?: number;
}

/** A request saved in a collection. */
export interface SavedRequest {
  id: string;
  name: string;
  method: HttpMethod;
  url: string;
  headers: ValueRow[] | Record<string, string>;
  query_params: ValueRow[] | Record<string, unknown>;
  body?: unknown;
  include_body?: boolean;
  include_for_generation?: boolean;
  include?: boolean;
  assertions?: Assertions;
  contract?: Record<string, unknown>;
  source_excerpt?: string;
  deprecated?: boolean;
  collection_id?: string;
  [key: string]: unknown;
}

/** A saved request collection. */
export interface Collection {
  id: string;
  name: string;
  requests: SavedRequest[];
  [key: string]: unknown;
}

/** One assertion instance. */
export interface AssertionConfig {
  id?: string;
  enabled: boolean;
  expected_status?: number;
  value?: string;
  path?: string;
  expected_value?: string;
  schema?: string;
}

/** Repeatable assertion groups used by playground runs and test cases. */
export interface Assertions {
  status: AssertionConfig[];
  body_contains: AssertionConfig[];
  jsonpath: AssertionConfig[];
  response_schema: AssertionConfig[];
}

/** One assertion outcome returned by the backend. */
export interface AssertionResult {
  type: string;
  passed: boolean;
  detail: string;
}

/** Result of sending one HTTP request. */
export interface HttpResult {
  status: number;
  headers: Record<string, string>;
  body: string;
  elapsed_ms: number;
  assertion_results?: AssertionResult[];
  assertions_passed?: boolean;
}

/** One response-to-request value mapping inside a flow step. */
export interface VariableMapping {
  mapping_id?: string;
  from: string;
  to: string;
  transform?: string;
  description?: string;
}

/** One step of a multi-endpoint flow test case. */
export interface FlowStep {
  step_id?: string;
  step_order: number;
  endpoint_id?: string | number;
  endpoint: ApiRequest & { id?: string; name?: string };
  description?: string;
  assertions?: Assertions;
  variable_mappings?: VariableMapping[];
  [key: string]: unknown;
}

/** A generated or manually authored test case. */
export interface TestCase {
  id: string;
  type: string;
  name: string;
  description?: string;
  request?: ApiRequest;
  is_flow?: boolean;
  steps?: FlowStep[];
  assertions?: Assertions;
  expected_status?: number | null;
  expected_body_contains?: string | null;
  case_kind?: string;
  case_collection_id?: string;
  case_collection_name?: string;
  manual_steps?: string[];
  manual_status?: string;
  manual_failure_reason?: string;
  business_requirements?: string;
  run_business_requirements?: string;
  generation_requirements?: string;
  technique_tags?: string[];
  requirement_refs?: string[];
  project_brief_versions?: unknown[];
  knowledge_hub_versions?: unknown[];
  knowledge_fact_ids?: string[];
  superseded_by_activity_id?: string | null;
  revision_id?: string | null;
  source_case_id?: string | number | null;
  source_endpoint_id?: string;
  source_endpoint_name?: string;
  created_at?: string;
  [key: string]: unknown;
}

/** A reusable named selection of test cases. */
export interface TestRun {
  id: string;
  name: string;
  case_ids: string[];
  [key: string]: unknown;
}

/** One named release revision. */
export interface TestCaseRevision {
  id: string;
  label: string;
  notes?: string;
  case_ids?: string[];
  created_at?: string;
  [key: string]: unknown;
}

/** A project summary from the list route, or the full detail payload. */
export interface Project {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  collections?: Collection[];
  endpoints?: SavedRequest[];
  test_cases?: TestCase[];
  test_runs?: TestRun[];
  test_case_revisions?: TestCaseRevision[];
  generation_order_ids?: string[];
  [key: string]: unknown;
}

/** A source cited by one assistant reply. */
export interface ChatSource {
  type?: string;
  id?: string;
  name?: string;
  method?: string;
  url?: string;
  collection_id?: string;
  collection_name?: string;
  scope_id?: string;
  status?: string;
  [key: string]: unknown;
}

/** One chat message. */
export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  ordinal: number;
  created_at?: string;
  knowledge_sources?: ChatSource[];
  endpoint_sources?: ChatSource[];
  provider_metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

/** One conversation in a project. */
export interface ChatThread {
  id: string;
  project_id: string;
  title: string;
  model?: string | null;
  messages?: ChatMessage[];
  context_summary?: string;
  feature_brief?: string;
  archived?: boolean;
  created_at?: string;
  updated_at?: string;
  summary_through_ordinal?: number;
  [key: string]: unknown;
}

/** One Knowledge Hub page. */
export interface KnowledgeHubPage {
  id: string;
  project_id: string;
  scope_type: 'project' | 'feature' | 'microservice';
  name: string;
  current_content: string;
  current_version_number: number;
  microservice_scope_ids?: string[];
  related_feature_ids?: string[];
  [key: string]: unknown;
}

/** One immutable Knowledge Hub page version. */
export interface KnowledgeHubVersion {
  id: string;
  version_number: number;
  content: string;
  created_at?: string;
  source_thread_id?: string | null;
  [key: string]: unknown;
}

/** One clarifications question returned with a generation result. */
export interface ClarificationQuestion {
  id?: string;
  question?: string;
  why?: string;
  text?: string;
  [key: string]: unknown;
}

/** One requirement and whether the generated suite covers it. */
export interface RequirementCoverage {
  requirement?: string;
  requirement_id?: string;
  covered?: boolean;
  note?: string;
  case_ids?: string[];
  [key: string]: unknown;
}

/** Coverage report returned alongside generated cases. */
export interface CoverageSummary {
  requirements?: RequirementCoverage[];
  unsupported_claims?: string[];
  note?: string;
  [key: string]: unknown;
}

/** One generation action from the activity log. */
export interface GenerationActivity {
  id: string;
  project_id: string;
  project_name?: string;
  action?: string;
  mode?: string;
  status?: string;
  timestamp?: string;
  created_at?: string;
  provider?: string;
  model?: string;
  finish_reason?: string;
  usage?: Record<string, unknown>;
  error?: string;
  gist?: string;
  prompt_messages?: unknown[];
  raw_response?: string;
  response_text?: string;
  coverage_summary?: CoverageSummary;
  clarification_questions?: ClarificationQuestion[];
  clarification_answers?: Record<string, string>;
  generated_case_ids?: string[];
  superseded_by_activity_id?: string | null;
  revision_id?: string | null;
  release_label?: string;
  [key: string]: unknown;
}

/** One knowledge-extraction event. */
export interface KnowledgeActivity {
  id: string;
  project_id: string;
  event?: string;
  source_type?: string;
  status?: string;
  created_at?: string;
  page_count?: number;
  proposal_count?: number;
  [key: string]: unknown;
}

/** Envelope returned by a generation route. */
export interface GenerationResponse {
  test_cases: TestCase[];
  clarification_questions?: ClarificationQuestion[];
  coverage_summary?: CoverageSummary | null;
  activity?: GenerationActivity | null;
}

/** One page of a list route.
 *
 * Generic so each caller keeps its own item type instead of falling back to
 * unknown at the call site.
 */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}


/** Result of parsing a pasted cURL command. */
export interface ParsedCurl {
  method?: string;
  url?: string;
  headers?: Record<string, string> | ValueRow[];
  query_params?: Record<string, unknown> | ValueRow[];
  body?: unknown;
  [key: string]: unknown;
}

/** Result of executing one saved case, including per-step detail. */
export interface ExecutionResult {
  test_case_id?: string;
  status: 'passed' | 'failed' | 'error';
  assertion_detail?: string;
  request_url?: string;
  request_method?: string;
  request_headers?: Record<string, string>;
  request_query_params?: Record<string, string>;
  request_body?: unknown;
  response_status?: number | null;
  response_headers?: Record<string, string>;
  response_body?: string | null;
  latency_ms?: number;
  manual_result?: boolean;
  failure_reason?: string;
  step_results?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

/** One versioned project brief or Knowledge Hub page. */
export interface BriefScope {
  id: string;
  project_id?: string;
  scope_type: 'project' | 'feature' | 'microservice';
  name: string;
  current_version_id?: string | null;
  current_version_number?: number | null;
  current_content?: string | null;
  current_version_created_at?: string | null;
  version_count?: number;
  microservice_scope_ids?: string[];
  related_feature_ids?: string[];
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

/** One immutable version of a brief scope. */
export interface BriefVersion {
  id: string;
  scope_id?: string;
  version_number: number;
  content: string;
  source_thread_id?: string | null;
  is_current?: boolean;
  created_at?: string;
  [key: string]: unknown;
}

/** One Markdown section that changed between two versions. */
export interface SectionDiff {
  section?: string;
  diff?: string;
  [key: string]: unknown;
}

/** One unsaved proposed page returned by the Knowledge Hub draft route. */
export interface HubDraftPage {
  scope_id: string;
  scope_name?: string;
  scope_type?: string;
  current_version_number?: number | null;
  current_content?: string;
  draft: string;
  section_diffs?: SectionDiff[];
  provider_metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

/** Envelope returned when the model prepares Hub page drafts from a thread. */
export interface HubDraftResponse {
  source_thread_id: string;
  draft_event_id?: string | null;
  pages: HubDraftPage[];
}
