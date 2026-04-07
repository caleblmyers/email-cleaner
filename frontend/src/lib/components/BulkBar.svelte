<script lang="ts">
	import * as api from '$lib/api/client';
	import { selection } from '$lib/stores/selection.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { loading } from '$lib/stores/loading.svelte';
	import { Button } from '$lib/components/ui/button';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Input } from '$lib/components/ui/input';

	let { onRefresh, onShowMove }: {
		onRefresh: () => void;
		onShowMove: () => void;
	} = $props();

	let confirmOpen = $state(false);
	let confirmAction = $state('');
	let confirmInput = $state('');

	const needsTypedConfirm = $derived(selection.count >= 100);

	function showConfirm(action: string) {
		confirmAction = action;
		confirmInput = '';
		confirmOpen = true;
	}

	async function executeAction(action: string) {
		const ids = selection.toArray();
		if (ids.length === 0) return;
		confirmOpen = false;

		const label = action.charAt(0).toUpperCase() + action.slice(1);
		loading.show(`${label}ing ${ids.length} emails...`);
		try {
			let result: api.BulkResult;
			if (action === 'delete') result = await api.bulkDelete(ids);
			else if (action === 'archive') result = await api.bulkArchive(ids);
			else if (action === 'save') {
				const r = await api.bulkSave(ids);
				loading.hide();
				toast.show(`Saved ${r.success} emails to ${r.saved_to}`);
				return;
			} else return;

			loading.hide();
			toast.show(`${result.success} ${action}d` + (result.failed ? `, ${result.failed} failed` : ''));
			selection.clear();
			onRefresh();
		} catch (e: any) { loading.hide(); toast.error(e.message); }
	}

	async function doMark(read: boolean) {
		const ids = selection.toArray();
		loading.show(read ? 'Marking read...' : 'Marking unread...');
		try {
			const r = await api.bulkMark(ids, read);
			loading.hide();
			toast.show(`Marked ${r.success} as ${read ? 'read' : 'unread'}`);
			selection.clear();
			onRefresh();
		} catch (e: any) { loading.hide(); toast.error(e.message); }
	}
</script>

{#if selection.count > 0}
	<div class="fixed bottom-0 left-0 right-0 bg-zinc-900 text-white px-6 py-3 flex items-center gap-4 flex-wrap shadow-[0_-2px_12px_rgba(0,0,0,0.2)] z-50">
		<span class="font-semibold text-sm">{selection.count} selected</span>
		<div class="flex gap-2 flex-wrap">
			<Button size="sm" variant="destructive" onclick={() => showConfirm('delete')}>Delete</Button>
			<Button size="sm" onclick={() => showConfirm('archive')}>Archive</Button>
			<Button size="sm" variant="secondary" onclick={onShowMove}>Move to...</Button>
			<Button size="sm" variant="secondary" onclick={() => executeAction('save')}>Save</Button>
			<Button size="sm" variant="outline" class="text-white border-zinc-600 hover:bg-zinc-800" onclick={() => doMark(true)}>Read</Button>
			<Button size="sm" variant="outline" class="text-white border-zinc-600 hover:bg-zinc-800" onclick={() => doMark(false)}>Unread</Button>
			<Button size="sm" variant="ghost" class="text-zinc-400 hover:text-white" onclick={() => selection.clear()}>Clear</Button>
		</div>
	</div>
{/if}

<Dialog.Root bind:open={confirmOpen}>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Confirm {confirmAction}</Dialog.Title>
			<Dialog.Description>
				{#if confirmAction === 'delete'}
					Trash {selection.count} email(s)? Gmail auto-empties trash after 30 days.
				{:else if confirmAction === 'archive'}
					Archive {selection.count} email(s)? They will be removed from your inbox.
				{/if}
			</Dialog.Description>
		</Dialog.Header>
		{#if needsTypedConfirm}
			<Input bind:value={confirmInput} placeholder='Type "{confirmAction}" to confirm' autocomplete="off" />
		{/if}
		<Dialog.Footer>
			<Button variant="outline" onclick={() => confirmOpen = false}>Cancel</Button>
			<Button variant="destructive"
				disabled={needsTypedConfirm && confirmInput.toLowerCase() !== confirmAction}
				onclick={() => executeAction(confirmAction)}>
				Confirm
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
