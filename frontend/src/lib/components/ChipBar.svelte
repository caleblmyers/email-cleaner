<script lang="ts">
	import type { GroupSummary, Stats, Category } from '$lib/api/client';
	import { Badge } from '$lib/components/ui/badge';

	let { groups, stats, categories, groupBy }: {
		groups: GroupSummary[];
		stats: Stats;
		categories: Category[];
		groupBy: string;
	} = $props();

	const colorMap = $derived(
		Object.fromEntries(categories.map(c => [c.name, c.color]))
	);
</script>

{#if groups.length > 0}
	<div class="flex flex-wrap gap-1.5 mb-5">
		{#each groups as group}
			{#if stats[group.name]}
				{@const color = groupBy === 'category' ? colorMap[group.name] : ''}
				{#if color}
					<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs text-white" style="background:{color}">
						{group.name} <strong>{stats[group.name].count}</strong>
						<span class="opacity-75">{stats[group.name].total_mb} MB</span>
					</span>
				{:else}
					<Badge variant="secondary" class="gap-1">
						{group.name} <strong>{stats[group.name].count}</strong>
						<span class="opacity-60 text-[10px]">{stats[group.name].total_mb} MB</span>
					</Badge>
				{/if}
			{/if}
		{/each}
	</div>
{/if}
