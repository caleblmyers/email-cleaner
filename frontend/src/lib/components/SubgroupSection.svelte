<script lang="ts">
	import * as api from '$lib/api/client';
	import type { Email, GroupSummary } from '$lib/api/client';
	import { selection } from '$lib/stores/selection.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import EmailTable from './EmailTable.svelte';
	import { ChevronRight } from 'lucide-svelte';

	let { subgroup, groupBy, groupName, thenBy }: {
		subgroup: GroupSummary;
		groupBy: string;
		groupName: string;
		thenBy: string;
	} = $props();

	let open = $state(false);
	let emails = $state<Email[]>([]);
	let totalEmails = $state(0);
	let currentPage = $state(1);
	const perPage = 50;
	let loadingState = $state(false);

	async function loadPage(page: number) {
		loadingState = true;
		try {
			const r = await api.getSubgroupEmails(groupBy, groupName, thenBy, subgroup.name, page, perPage);
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
		if (open && emails.length === 0) loadPage(1);
	}

	async function selectSubgroup(e: Event) {
		e.stopPropagation();
		try {
			const r = await api.getSubgroupEmails(groupBy, groupName, thenBy, subgroup.name, 1, 10000);
			selection.addAll(r.emails.map(e => e.id));
		} catch (err: any) {
			toast.error(err.message);
		}
	}
</script>

<div class="border-t">
	<button
		class="w-full flex items-center gap-3 px-4 py-2 pl-10 hover:bg-muted/50 transition-colors text-left"
		onclick={toggle}>
		<Checkbox onCheckedChange={() => {}} onclick={selectSubgroup} />
		<ChevronRight class="h-3.5 w-3.5 text-muted-foreground transition-transform {open ? 'rotate-90' : ''}" />
		<span class="text-sm">{subgroup.name}</span>
		<Badge variant="secondary" class="text-xs">{subgroup.count}</Badge>
	</button>

	{#if open}
		<div class="pl-6">
			{#if loadingState}
				<div class="flex items-center justify-center py-4">
					<div class="animate-spin h-4 w-4 border-2 border-muted border-t-primary rounded-full"></div>
					<span class="ml-2 text-xs text-muted-foreground">Loading...</span>
				</div>
			{:else}
				<EmailTable {emails} total={totalEmails} page={currentPage} {perPage} onPageChange={loadPage} />
			{/if}
		</div>
	{/if}
</div>
