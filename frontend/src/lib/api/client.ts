const BASE = '';

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
	const res = await fetch(`${BASE}${path}`, {
		headers: { 'Content-Type': 'application/json', ...opts.headers as Record<string, string> },
		...opts
	});
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `${res.status} ${res.statusText}`);
	}
	return res.json();
}

// --- Emails ---

export interface Email {
	id: string;
	thread_id: string;
	sender: string;
	sender_email: string;
	subject: string;
	snippet: string;
	date: number;
	size_estimate: number;
	is_read: boolean;
	label_ids: string; // JSON-encoded string[] from SQLite
	category: string | null;
	confidence: number | null;
	reasoning: string | null;
	_date_fmt?: string;
	_size_fmt?: string;
	_confidence_pct?: number;
}

export interface FetchResult {
	fetched: number;
	next_page_token: string | null;
}

export interface ClassifyResult {
	classified: number;
	usage: { input_tokens: number; output_tokens: number; total_cost: number };
}

export interface BulkResult {
	success: number;
	failed: number;
	succeeded_ids: string[];
	errors: { id: string; error: string }[];
}

export interface GroupResult {
	emails: Email[];
	total: number;
	page: number;
	per_page: number;
}

export interface Stats {
	[group: string]: { count: number; total_mb: number };
}

export interface AiUsage {
	total_input_tokens: number;
	total_output_tokens: number;
	total_cost: number;
	total_emails_classified: number;
	total_runs: number;
}

export function fetchEmails(maxResults: number, fetchAll: boolean) {
	return request<FetchResult>('/emails/fetch', {
		method: 'POST',
		body: JSON.stringify({ max_results: maxResults, fetch_all: fetchAll })
	});
}

export function classifyEmails(limit?: number) {
	const body = limit && limit > 0 ? { limit } : {};
	return request<ClassifyResult>('/emails/classify', {
		method: 'POST',
		body: JSON.stringify(body)
	});
}

export function getGroupEmails(groupBy: string, groupName: string, page = 1, perPage = 50) {
	const params = new URLSearchParams({ group_by: groupBy, group_name: groupName, page: String(page), per_page: String(perPage) });
	return request<GroupResult>(`/emails/group?${params}`);
}

export function getSubgroupSummaries(groupBy: string, groupName: string, thenBy: string) {
	const params = new URLSearchParams({ group_by: groupBy, group_name: groupName, then_by: thenBy });
	return request<{ subgroups: GroupSummary[] }>(`/emails/group/subgroups?${params}`);
}

export function getSubgroupEmails(groupBy: string, groupName: string, thenBy: string, subgroupName: string, page = 1, perPage = 50) {
	const params = new URLSearchParams({ group_by: groupBy, group_name: groupName, then_by: thenBy, subgroup_name: subgroupName, page: String(page), per_page: String(perPage) });
	return request<GroupResult>(`/emails/subgroup?${params}`);
}

export function getStats() {
	return request<Stats>('/emails/stats');
}

export function getAiUsage() {
	return request<AiUsage>('/emails/ai-usage');
}

// --- Bulk actions ---

export function bulkDelete(ids: string[]) {
	return request<BulkResult>('/emails/actions/delete', { method: 'POST', body: JSON.stringify({ email_ids: ids }) });
}

export function bulkArchive(ids: string[]) {
	return request<BulkResult>('/emails/actions/archive', { method: 'POST', body: JSON.stringify({ email_ids: ids }) });
}

export function bulkMove(ids: string[], labelId: string) {
	return request<BulkResult>('/emails/actions/move', { method: 'POST', body: JSON.stringify({ email_ids: ids, label_id: labelId }) });
}

export function bulkMark(ids: string[], read: boolean) {
	return request<BulkResult>('/emails/actions/mark', { method: 'POST', body: JSON.stringify({ email_ids: ids, read }) });
}

export function bulkSave(ids: string[]) {
	return request<BulkResult & { saved_to: string }>('/emails/actions/save', { method: 'POST', body: JSON.stringify({ email_ids: ids }) });
}

// --- Categories ---

export interface Category {
	id: number;
	name: string;
	description: string;
	color: string;
	sort_order: number;
}

export function getCategories() {
	return request<Category[]>('/categories/');
}

export function createCategory(name: string, description: string, color: string) {
	return request<Category>('/categories/', { method: 'POST', body: JSON.stringify({ name, description, color }) });
}

export function updateCategory(id: number, fields: Partial<Pick<Category, 'name' | 'description' | 'color'>>) {
	return request<Category>(`/categories/${id}`, { method: 'PUT', body: JSON.stringify(fields) });
}

export function deleteCategory(id: number) {
	return request<{ deleted: boolean }>(`/categories/${id}`, { method: 'DELETE' });
}

// --- Gmail labels ---

export interface GmailLabel {
	id: string;
	name: string;
	type: string;
}

export function getLabels() {
	return request<GmailLabel[]>('/labels/');
}

export function createLabel(name: string) {
	return request<GmailLabel>('/labels/', { method: 'POST', body: JSON.stringify({ name }) });
}

export function renameLabel(id: string, name: string) {
	return request<GmailLabel>(`/labels/${id}`, { method: 'PUT', body: JSON.stringify({ name }) });
}

export function deleteLabel(id: string) {
	return request<{ deleted: boolean }>(`/labels/${id}`, { method: 'DELETE' });
}

// --- Dashboard (server-rendered data) ---

export interface GroupSummary {
	name: string;
	count: number;
}

export interface DashboardData {
	stats: Stats;
	total: number;
	unclassified_count: number;
	ai_usage: AiUsage;
	group_summaries: GroupSummary[];
	categories: Category[];
}

export function getDashboard(groupBy: string, thenBy?: string) {
	const params = new URLSearchParams({ group_by: groupBy });
	if (thenBy) params.set('then_by', thenBy);
	return request<DashboardData>(`/emails/dashboard?${params}`);
}
