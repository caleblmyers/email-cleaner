<script lang="ts">
	import * as api from '$lib/api/client';
	import type { Category } from '$lib/api/client';
	import { toast } from '$lib/stores/toast.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Badge } from '$lib/components/ui/badge';
	import * as Dialog from '$lib/components/ui/dialog';
	import { X, Pencil, Trash2, Plus } from 'lucide-svelte';

	let { onChanged }: { onChanged: () => void } = $props();

	let isOpen = $state(false);
	let categories = $state<Category[]>([]);
	let editingId = $state<number | null>(null);
	let editName = $state('');
	let editColor = $state('');
	let newName = $state('');
	let newDesc = $state('');
	let newColor = $state('#718096');

	export function open() {
		isOpen = true;
		reload();
	}

	async function reload() { categories = await api.getCategories(); }

	async function create() {
		if (!newName.trim()) return;
		try {
			await api.createCategory(newName.trim(), newDesc.trim(), newColor);
			newName = ''; newDesc = ''; newColor = '#718096';
			await reload(); onChanged();
		} catch (e: any) { toast.error(e.message); }
	}

	function startEdit(cat: Category) {
		editingId = cat.id; editName = cat.name; editColor = cat.color;
	}

	async function saveEdit(id: number) {
		try {
			await api.updateCategory(id, { name: editName.trim(), color: editColor });
			editingId = null; await reload(); onChanged();
		} catch (e: any) { toast.error(e.message); }
	}

	async function remove(cat: Category) {
		if (!confirm(`Delete "${cat.name}"? Emails will be moved to Uncategorized.`)) return;
		try { await api.deleteCategory(cat.id); await reload(); onChanged(); }
		catch (e: any) { toast.error(e.message); }
	}

	async function addItem(cat: Category) {
		const item = prompt('New descriptor item:');
		if (!item?.trim()) return;
		const desc = cat.description ? `${cat.description}, ${item.trim()}` : item.trim();
		try { await api.updateCategory(cat.id, { description: desc }); await reload(); onChanged(); }
		catch (e: any) { toast.error(e.message); }
	}

	async function removeItem(cat: Category, item: string) {
		const items = cat.description.split(',').map(s => s.trim()).filter(s => s && s !== item);
		try { await api.updateCategory(cat.id, { description: items.join(', ') }); await reload(); onChanged(); }
		catch (e: any) { toast.error(e.message); }
	}
</script>

<Dialog.Root bind:open={isOpen}>
	<Dialog.Content class="max-w-xl">
		<Dialog.Header>
			<Dialog.Title>Manage Categories</Dialog.Title>
			<Dialog.Description>Add, edit, or remove AI classification categories. Each has descriptor items that guide the classifier.</Dialog.Description>
		</Dialog.Header>

		<div class="space-y-2 max-h-[50vh] overflow-y-auto">
			{#each categories as cat (cat.id)}
				<div class="border rounded-lg p-3" class:border-primary={editingId === cat.id}>
					{#if editingId === cat.id}
						<div class="flex items-center gap-2">
							<input type="color" bind:value={editColor} class="w-8 h-8 rounded border cursor-pointer">
							<Input bind:value={editName} class="flex-1"
								onkeydown={(e) => { if (e.key === 'Enter') saveEdit(cat.id); }} />
							<Button size="sm" onclick={() => saveEdit(cat.id)}>Save</Button>
							<Button size="sm" variant="ghost" onclick={() => editingId = null}>Cancel</Button>
						</div>
					{:else}
						<div class="flex items-center gap-2">
							<span class="w-3.5 h-3.5 rounded-full shrink-0" style="background:{cat.color}"></span>
							<span class="font-medium text-sm">{cat.name}</span>
							<div class="ml-auto flex gap-1">
								<Button size="icon" variant="ghost" class="h-7 w-7" onclick={() => startEdit(cat)}>
									<Pencil class="h-3.5 w-3.5" />
								</Button>
								{#if cat.name !== 'Uncategorized'}
									<Button size="icon" variant="ghost" class="h-7 w-7 text-destructive" onclick={() => remove(cat)}>
										<Trash2 class="h-3.5 w-3.5" />
									</Button>
								{/if}
							</div>
						</div>
					{/if}
					<div class="flex flex-wrap gap-1.5 mt-2">
						{#each (cat.description || '').split(',').map(s => s.trim()).filter(Boolean) as item}
							<Badge variant="secondary" class="gap-1 pr-1">
								{item}
								<button class="ml-0.5 hover:text-destructive transition-colors" onclick={() => removeItem(cat, item)}>
									<X class="h-3 w-3" />
								</button>
							</Badge>
						{/each}
						<button class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border border-dashed text-primary hover:border-primary transition-colors"
							onclick={() => addItem(cat)}>
							<Plus class="h-3 w-3" /> add
						</button>
					</div>
				</div>
			{/each}
		</div>

		<div class="border-t pt-4 mt-4 space-y-2">
			<span class="font-medium text-sm">Add New Category</span>
			<div class="flex gap-2 items-center">
				<Input bind:value={newName} placeholder="Category name" class="flex-1" />
				<input type="color" bind:value={newColor} class="w-8 h-8 rounded border cursor-pointer">
				<Button onclick={create}>Add</Button>
			</div>
			<Input bind:value={newDesc} placeholder="Descriptor items (e.g. invoices, bank statements)" />
		</div>
	</Dialog.Content>
</Dialog.Root>
