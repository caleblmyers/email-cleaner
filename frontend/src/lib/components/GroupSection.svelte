<script lang="ts">
	import * as api from '$lib/api/client';
	import type { Email, GroupSummary, Stats } from '$lib/api/client';
	import { selection } from '$lib/stores/selection.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import EmailTable from './EmailTable.svelte';
	import { ChevronRight } from 'lucide-svelte';

	let { group, stats, groupBy, thenBy }: {
		group: GroupSummary;
		stats: Stats;
		groupBy: string;
		thenBy: string;
	} = $props();

	let open = $state(false);
	let emails = $state<Email[] | null>(null);
	let loadingState = $state(false);

	async function load() {
		if (emails || loadingState) return;
		loadingState = true;
		try {
			const r = await api.getGroupEmails(groupBy, group.name);
			emails = r.emails;
		} catch (e: any) {
			toast.error('Failed to load: ' + e.message);
		} finally {
			loadingState = false;
		}
	}

	function toggle() {
		open = !open;
		if (open) load();
	}

	async function selectGroup(e: Event) {
		e.stopPropagation();
		try {
			const r = await api.getGroupEmails(groupBy, group.name);
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
			{#if loadingState}
				<div class="flex items-center justify-center py-8">
					<div class="animate-spin h-5 w-5 border-2 border-muted border-t-primary rounded-full"></div>
					<span class="ml-2 text-sm text-muted-foreground">Loading...</span>
				</div>
			{:else if emails}
				<EmailTable {emails} />
			{/if}
		</div>
	{/if}
</div>
