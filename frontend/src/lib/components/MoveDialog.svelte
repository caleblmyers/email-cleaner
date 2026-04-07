<script lang="ts">
	import * as api from '$lib/api/client';
	import type { GmailLabel } from '$lib/api/client';
	import { selection } from '$lib/stores/selection.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { loading } from '$lib/stores/loading.svelte';
	import { Button } from '$lib/components/ui/button';
	import * as Dialog from '$lib/components/ui/dialog';

	let { onRefresh }: { onRefresh: () => void } = $props();

	let isOpen = $state(false);
	let labels = $state<GmailLabel[]>([]);
	let selectedLabel = $state('');

	export function open() {
		selectedLabel = '';
		isOpen = true;
		api.getLabels().then(l => labels = l).catch(() => {});
	}

	async function doMove() {
		if (!selectedLabel) { toast.error('Please select a label'); return; }
		isOpen = false;
		const ids = selection.toArray();
		loading.show(`Moving ${ids.length} emails...`);
		try {
			const r = await api.bulkMove(ids, selectedLabel);
			loading.hide();
			toast.show(`Moved ${r.success} emails`);
			selection.clear();
			onRefresh();
		} catch (e: any) { loading.hide(); toast.error(e.message); }
	}
</script>

<Dialog.Root bind:open={isOpen}>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Move to Label</Dialog.Title>
			<Dialog.Description>Select a Gmail label to move {selection.count} email(s) to.</Dialog.Description>
		</Dialog.Header>
		<select bind:value={selectedLabel}
			class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
			<option value="">-- Select a label --</option>
			{#each labels as label}
				<option value={label.id}>{label.name}</option>
			{/each}
		</select>
		<Dialog.Footer>
			<Button variant="outline" onclick={() => isOpen = false}>Cancel</Button>
			<Button onclick={doMove}>Move</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
