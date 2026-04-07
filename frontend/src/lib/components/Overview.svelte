<script lang="ts">
	import type { AiUsage } from '$lib/api/client';
	import * as Card from '$lib/components/ui/card';

	let { total, unclassifiedCount, aiUsage }: {
		total: number;
		unclassifiedCount: number;
		aiUsage: AiUsage;
	} = $props();
</script>

<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
	<Card.Root>
		<Card.Content class="p-4 text-center">
			<div class="text-3xl font-bold text-primary">{total}</div>
			<div class="text-xs text-muted-foreground mt-1">emails cached</div>
		</Card.Content>
	</Card.Root>
	{#if unclassifiedCount > 0}
		<Card.Root>
			<Card.Content class="p-4 text-center">
				<div class="text-3xl font-bold text-destructive">{unclassifiedCount}</div>
				<div class="text-xs text-muted-foreground mt-1">unclassified</div>
			</Card.Content>
		</Card.Root>
	{/if}
	{#if aiUsage.total_runs > 0}
		<Card.Root>
			<Card.Content class="p-4 text-center">
				<div class="text-3xl font-bold text-primary">{aiUsage.total_emails_classified}</div>
				<div class="text-xs text-muted-foreground mt-1">classified</div>
			</Card.Content>
		</Card.Root>
		<Card.Root>
			<Card.Content class="p-4 text-center">
				<div class="text-3xl font-bold text-primary">${aiUsage.total_cost.toFixed(4)}</div>
				<div class="text-xs text-muted-foreground mt-1">AI cost</div>
			</Card.Content>
		</Card.Root>
	{/if}
</div>
