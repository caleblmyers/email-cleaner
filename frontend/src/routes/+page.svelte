<script lang="ts">
	import { page } from '$app/state';
	import * as api from '$lib/api/client';
	import type { DashboardData } from '$lib/api/client';
	import Toolbar from '$lib/components/Toolbar.svelte';
	import Overview from '$lib/components/Overview.svelte';
	import ChipBar from '$lib/components/ChipBar.svelte';
	import GroupSection from '$lib/components/GroupSection.svelte';
	import BulkBar from '$lib/components/BulkBar.svelte';
	import MoveDialog from '$lib/components/MoveDialog.svelte';
	import CategoriesDialog from '$lib/components/CategoriesDialog.svelte';
	import LabelsDialog from '$lib/components/LabelsDialog.svelte';
	import * as Card from '$lib/components/ui/card';

	const GROUP_MODES: Record<string, string> = {
		category: 'AI Category',
		sender: 'Sender Domain',
		date: 'Date Range',
		read_status: 'Read / Unread',
		size: 'Size',
		label: 'Labels',
		frequency: 'Top Senders'
	};

	let groupBy = $derived(page.url.searchParams.get('group_by') || 'category');
	let thenBy = $derived(page.url.searchParams.get('then_by') || '');

	let data = $state<DashboardData | null>(null);
	let error = $state('');

	let moveDialog: MoveDialog;
	let categoriesDialog: CategoriesDialog;
	let labelsDialog: LabelsDialog;

	async function loadDashboard() {
		try {
			data = await api.getDashboard(groupBy, thenBy || undefined);
			error = '';
		} catch (e: any) {
			if (e.message.includes('401') || e.message.includes('Not authenticated')) {
				window.location.href = '/login';
				return;
			}
			error = e.message;
		}
	}

	$effect(() => {
		groupBy; thenBy;
		loadDashboard();
	});
</script>

<div class="min-h-screen bg-background">
	<!-- Header -->
	<header class="sticky top-0 z-40 bg-background border-b shadow-sm">
		<div class="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between">
			<span class="font-bold text-lg tracking-tight">&#9993; Email Cleaner</span>
			<a href="/auth/logout" class="text-sm text-muted-foreground hover:text-foreground transition-colors">Logout</a>
		</div>
		{#if data}
			<Toolbar
				{groupBy}
				{thenBy}
				groupModes={GROUP_MODES}
				onRefresh={loadDashboard}
				onOpenCategories={() => categoriesDialog.open()}
				onOpenLabels={() => labelsDialog.open()}
			/>
		{/if}
	</header>

	<!-- Main content -->
	<main class="max-w-7xl mx-auto px-4 py-6 pb-24">
		{#if error}
			<Card.Root class="text-center p-8">
				<Card.Content>
					<p class="text-destructive mb-4">Failed to load dashboard: {error}</p>
					<button class="underline text-primary" onclick={loadDashboard}>Retry</button>
				</Card.Content>
			</Card.Root>
		{:else if !data}
			<div class="flex items-center justify-center py-20">
				<div class="animate-spin h-8 w-8 border-4 border-muted border-t-primary rounded-full"></div>
				<span class="ml-3 text-muted-foreground">Loading dashboard...</span>
			</div>
		{:else}
			<Overview total={data.total} unclassifiedCount={data.unclassified_count} aiUsage={data.ai_usage} />
			<ChipBar groups={data.group_summaries} stats={data.stats} categories={data.categories} {groupBy} />

			{#each data.group_summaries as group (group.name)}
				<GroupSection {group} stats={data.stats} {groupBy} {thenBy} />
			{/each}

			{#if data.total === 0}
				<Card.Root class="text-center py-16">
					<Card.Content>
						<div class="text-5xl mb-4">&#9993;</div>
						<h3 class="text-xl font-semibold mb-2">No emails yet</h3>
						<p class="text-muted-foreground">Click <strong>Fetch</strong> above to load your inbox.</p>
					</Card.Content>
				</Card.Root>
			{:else if data.group_summaries.length === 0}
				<Card.Root class="text-center py-16">
					<Card.Content>
						<div class="text-5xl mb-4">&#128270;</div>
						<h3 class="text-xl font-semibold mb-2">Emails fetched but not categorized</h3>
						<p class="text-muted-foreground">Click <strong>Classify</strong> to run AI categorization.</p>
					</Card.Content>
				</Card.Root>
			{/if}
		{/if}
	</main>
</div>

<BulkBar onRefresh={loadDashboard} onShowMove={() => moveDialog.open()} />
<MoveDialog bind:this={moveDialog} onRefresh={loadDashboard} />
<CategoriesDialog bind:this={categoriesDialog} onChanged={loadDashboard} />
<LabelsDialog bind:this={labelsDialog} onChanged={loadDashboard} />
