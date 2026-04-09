<script lang="ts">
	import * as api from '$lib/api/client';
	import type { Email, GroupSummary, Stats } from '$lib/api/client';
	import { selection } from '$lib/stores/selection.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import EmailTable from './EmailTable.svelte';
	import SubgroupSection from './SubgroupSection.svelte';
	import { ChevronRight } from 'lucide-svelte';

	let { group, stats, groupBy, thenBy }: {
		group: GroupSummary;
		stats: Stats;
		groupBy: string;
		thenBy: string;
	} = $props();

	let open = $state(false);

	// Flat email list (no thenBy)
	let emails = $state<Email[]>([]);
	let totalEmails = $state(0);
	let currentPage = $state(1);
	const perPage = 50;

	// Subgroups (with thenBy)
	let subgroups = $state<GroupSummary[]>([]);

	let loadingState = $state(false);
	let loaded = $state(false);

	async function load() {
		if (loaded || loadingState) return;
		loadingState = true;
		try {
			if (thenBy) {
				const r = await api.getSubgroupSummaries(groupBy, group.name, thenBy);
				subgroups = r.subgroups;
			} else {
				const r = await api.getGroupEmails(groupBy, group.name, 1, perPage);
				emails = r.emails;
				totalEmails = r.total;
				currentPage = 1;
			}
			loaded = true;
		} catch (e: any) {
			toast.error('Failed to load: ' + e.message);
		} finally {
			loadingState = false;
		}
	}

	async function loadPage(page: number) {
		loadingState = true;
		try {
			const r = await api.getGroupEmails(groupBy, group.name, page, perPage);
			emails = r.emails;
			totalEmails = r.total;
			currentPage = page;
		} catch (e: any) {
			toast.error('Failed to load: ' + e.message);
		} finally {
			loadingState = false;
		}
	}

	function toggle() {
		open = !open;
		if (open && !loaded) load();
	}

	async function selectGroup(e: Event) {
		e.stopPropagation();
		try {
			const r = await api.getGroupEmails(groupBy, group.name, 1, 10000);
			selection.addAll(r.emails.map(e => e.id));
		} catch (err: any) {
			toast.error(err.message);
		}
	}

	const groupStat = $derived(stats[group.name]);
</script>

<div class="border rounded-lg mb-2 bg-card overflow-hidden" class:shadow-sm={open}>
	<button
		class="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors text-left"
		onclick={toggle}>
		<Checkbox onCheckedChange={() => {}} onclick={selectGroup} />
		<ChevronRight class="h-4 w-4 text-muted-foreground transition-transform {open ? 'rotate-90' : ''}" />
		<span class="font-semibold text-sm">{group.name}</span>
		<Badge variant="secondary" class="text-xs">{group.count}</Badge>
		{#if groupStat}
			<span class="text-xs text-muted-foreground ml-auto">{groupStat.total_mb} MB</span>
		{/if}
	</button>

	{#if open}
		<div class="border-t">
			{#if loadingState && !loaded}
				<div class="flex items-center justify-center py-8">
					<div class="animate-spin h-5 w-5 border-2 border-muted border-t-primary rounded-full"></div>
					<span class="ml-2 text-sm text-muted-foreground">Loading...</span>
				</div>
			{:else if thenBy && subgroups.length > 0}
				{#each subgroups as subgroup (subgroup.name)}
					<SubgroupSection {subgroup} {groupBy} groupName={group.name} {thenBy} />
				{/each}
			{:else if thenBy && loaded && subgroups.length === 0}
				<div class="py-6 text-center text-sm text-muted-foreground">No emails in this group.</div>
			{:else}
				<EmailTable {emails} total={totalEmails} page={currentPage} {perPage} onPageChange={loadPage} />
			{/if}
		</div>
	{/if}
</div>
