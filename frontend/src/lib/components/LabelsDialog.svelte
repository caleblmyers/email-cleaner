<script lang="ts">
	import * as api from '$lib/api/client';
	import type { GmailLabel } from '$lib/api/client';
	import { toast } from '$lib/stores/toast.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Pencil, Trash2 } from 'lucide-svelte';

	let { onChanged }: { onChanged: () => void } = $props();

	let isOpen = $state(false);
	let labels = $state<GmailLabel[]>([]);
	let editingId = $state<string | null>(null);
	let editName = $state('');
	let newName = $state('');

	export function open() {
		isOpen = true;
		reload();
	}

	async function reload() { labels = await api.getLabels(); }

	async function create() {
		if (!newName.trim()) return;
		try { await api.createLabel(newName.trim()); newName = ''; await reload(); onChanged(); }
		catch (e: any) { toast.error(e.message); }
	}

	function startEdit(label: GmailLabel) {
		editingId = label.id; editName = label.name;
	}

	async function saveEdit(id: string) {
		try { await api.renameLabel(id, editName.trim()); editingId = null; await reload(); onChanged(); }
		catch (e: any) { toast.error(e.message); }
	}

	async function remove(label: GmailLabel) {
		if (!confirm(`Delete Gmail label "${label.name}"? Emails will NOT be deleted.`)) return;
		try { await api.deleteLabel(label.id); await reload(); onChanged(); }
		catch (e: any) { toast.error(e.message); }
	}
</script>

<Dialog.Root bind:open={isOpen}>
	<Dialog.Content class="max-w-md">
		<Dialog.Header>
			<Dialog.Title>Manage Gmail Labels</Dialog.Title>
			<Dialog.Description>Create, rename, or delete labels in your Gmail account. Deleting a label does not delete emails.</Dialog.Description>
		</Dialog.Header>

		<div class="space-y-2 max-h-[50vh] overflow-y-auto">
			{#each labels as label (label.id)}
				<div class="border rounded-lg p-3" class:border-primary={editingId === label.id}>
					{#if editingId === label.id}
						<div class="flex items-center gap-2">
							<Input bind:value={editName} class="flex-1"
								onkeydown={(e) => { if (e.key === 'Enter') saveEdit(label.id); }} />
							<Button size="sm" onclick={() => saveEdit(label.id)}>Save</Button>
							<Button size="sm" variant="ghost" onclick={() => editingId = null}>Cancel</Button>
						</div>
					{:else}
						<div class="flex items-center gap-2">
							<span class="font-medium text-sm">{label.name}</span>
							<div class="ml-auto flex gap-1">
								<Button size="icon" variant="ghost" class="h-7 w-7" onclick={() => startEdit(label)}>
									<Pencil class="h-3.5 w-3.5" />
								</Button>
								<Button size="icon" variant="ghost" class="h-7 w-7 text-destructive" onclick={() => remove(label)}>
									<Trash2 class="h-3.5 w-3.5" />
								</Button>
							</div>
						</div>
					{/if}
				</div>
			{/each}

			{#if labels.length === 0}
				<p class="text-center text-sm text-muted-foreground py-4">No user-created labels in Gmail.</p>
			{/if}
		</div>

		<div class="border-t pt-4 mt-4">
			<span class="font-medium text-sm">Create New Label</span>
			<div class="flex gap-2 mt-2">
				<Input bind:value={newName} placeholder="Label name (e.g. Work/Projects)"
					onkeydown={(e) => { if (e.key === 'Enter') create(); }} class="flex-1" />
				<Button onclick={create}>Create</Button>
			</div>
		</div>
	</Dialog.Content>
</Dialog.Root>
