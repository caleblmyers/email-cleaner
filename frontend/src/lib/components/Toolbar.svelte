<script lang="ts">
	import * as api from '$lib/api/client';
	import { toast } from '$lib/stores/toast.svelte';
	import { loading } from '$lib/stores/loading.svelte';
	import { Button } from '$lib/components/ui/button';

	let {
		groupBy = 'category',
		thenBy = '',
		groupModes,
		onRefresh,
		onOpenCategories,
		onOpenLabels
	}: {
		groupBy: string;
		thenBy: string;
		groupModes: Record<string, string>;
		onRefresh: () => void;
		onOpenCategories: () => void;
		onOpenLabels: () => void;
	} = $props();

	let fetchCount = $state('50');
	let classifyCount = $state('20');

	async function doFetch() {
		const fetchAll = fetchCount === 'all';
		const max = fetchAll ? 500 : parseInt(fetchCount);
		loading.show(fetchAll ? 'Fetching all emails...' : `Fetching up to ${max} emails...`);
		try {
			const r = await api.fetchEmails(max, fetchAll);
			loading.hide();
			if (r.fetched === 0) toast.info('No new emails to fetch');
			else { toast.show(`Fetched ${r.fetched} emails`); onRefresh(); }
		} catch (e: any) { loading.hide(); toast.error(e.message); }
	}

	async function doClassify() {
		const limit = parseInt(classifyCount);
		loading.show(`Classifying ${limit > 0 ? limit : 'all'} emails...`);
		try {
			const r = await api.classifyEmails(limit > 0 ? limit : undefined);
			loading.hide();
			toast.show(`Classified ${r.classified} emails ($${r.usage.total_cost.toFixed(4)})`);
			onRefresh();
		} catch (e: any) { loading.hide(); toast.error(e.message); }
	}

	function changeGroupBy(val: string) {
		const url = new URL(window.location.href);
		url.searchParams.set('group_by', val);
		if (url.searchParams.get('then_by') === val) url.searchParams.delete('then_by');
		window.location.href = url.toString();
	}

	function changeThenBy(val: string) {
		const url = new URL(window.location.href);
		if (val) url.searchParams.set('then_by', val);
		else url.searchParams.delete('then_by');
		window.location.href = url.toString();
	}
</script>

<div class="border-t bg-card px-4 py-2">
	<div class="max-w-7xl mx-auto flex items-center gap-4 flex-wrap">
		<div class="flex items-center gap-1">
			<Button size="sm" onclick={doFetch}>Fetch</Button>
			<select bind:value={fetchCount} class="h-8 text-xs rounded-md border border-input bg-background px-2">
				<option value="50">50</option>
				<option value="100">100</option>
				<option value="200">200</option>
				<option value="500">500</option>
				<option value="all">All</option>
			</select>
		</div>
		<div class="flex items-center gap-1">
			<Button size="sm" variant="secondary" onclick={doClassify}>Classify</Button>
			<select bind:value={classifyCount} class="h-8 text-xs rounded-md border border-input bg-background px-2">
				<option value="20">20</option>
				<option value="50">50</option>
				<option value="100">100</option>
				<option value="0">All</option>
			</select>
		</div>

		<div class="flex items-center gap-2 ml-auto">
			<span class="text-xs text-muted-foreground">Group by</span>
			<select class="h-8 text-xs rounded-md border border-input bg-background px-2" onchange={(e) => changeGroupBy(e.currentTarget.value)}>
				{#each Object.entries(groupModes) as [val, label]}
					<option value={val} selected={val === groupBy}>{label}</option>
				{/each}
			</select>
			<span class="text-xs text-muted-foreground">then</span>
			<select class="h-8 text-xs rounded-md border border-input bg-background px-2" onchange={(e) => changeThenBy(e.currentTarget.value)}>
				<option value="">None</option>
				{#each Object.entries(groupModes) as [val, label]}
					{#if val !== groupBy}
						<option value={val} selected={val === thenBy}>{label}</option>
					{/if}
				{/each}
			</select>
		</div>

		<div class="flex items-center gap-1">
			<Button size="sm" variant="outline" onclick={onOpenCategories}>Categories</Button>
			<Button size="sm" variant="outline" onclick={onOpenLabels}>Labels</Button>
		</div>
	</div>
</div>
