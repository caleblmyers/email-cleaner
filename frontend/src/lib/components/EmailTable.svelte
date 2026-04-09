<script lang="ts">
	import type { Email } from '$lib/api/client';
	import { selection } from '$lib/stores/selection.svelte';
	import * as Table from '$lib/components/ui/table';
	import { Button } from '$lib/components/ui/button';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { ChevronLeft, ChevronRight } from 'lucide-svelte';

	let { emails, total = 0, page = 1, perPage = 50, onPageChange }: {
		emails: Email[];
		total?: number;
		page?: number;
		perPage?: number;
		onPageChange?: (page: number) => void;
	} = $props();

	const totalPages = $derived(Math.ceil(total / perPage));
	const showPagination = $derived(total > perPage);

	function fmtDate(ts: number): string {
		if (!ts) return '';
		const d = new Date(ts * 1000);
		const now = new Date();
		if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
		if (d.getFullYear() === now.getFullYear()) return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
		return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
	}

	function fmtSize(bytes: number): string {
		if (!bytes) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}
</script>

<Table.Root>
	<Table.Header>
		<Table.Row>
			<Table.Head class="w-8"></Table.Head>
			<Table.Head class="w-40">From</Table.Head>
			<Table.Head>Subject</Table.Head>
			<Table.Head class="w-20 hidden md:table-cell">Date</Table.Head>
			<Table.Head class="w-12 hidden md:table-cell text-center">AI</Table.Head>
			<Table.Head class="w-16 hidden md:table-cell text-right">Size</Table.Head>
		</Table.Row>
	</Table.Header>
	<Table.Body>
		{#each emails as email (email.id)}
			<Table.Row class={!email.is_read ? 'font-semibold' : ''}>
				<Table.Cell>
					<Checkbox
						checked={selection.has(email.id)}
						onCheckedChange={() => selection.toggle(email.id)} />
				</Table.Cell>
				<Table.Cell class="max-w-[160px] truncate" title={email.sender_email}>
					{(email.sender || email.sender_email || 'Unknown').slice(0, 28)}
				</Table.Cell>
				<Table.Cell>
					<span>{email.subject || '(no subject)'}</span>
					{#if email.snippet}
						<span class="text-xs text-muted-foreground ml-1">— {email.snippet.slice(0, 80)}</span>
					{/if}
				</Table.Cell>
				<Table.Cell class="hidden md:table-cell text-xs text-muted-foreground whitespace-nowrap">
					{fmtDate(email.date)}
				</Table.Cell>
				<Table.Cell class="hidden md:table-cell text-center">
					{#if email.confidence}
						{@const pct = Math.round(email.confidence * 100)}
						<span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold text-white
							{email.confidence >= 0.8 ? 'bg-green-600' : email.confidence >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'}"
							title={email.reasoning || ''}>
							{pct}%
						</span>
					{:else}
						<span class="text-muted-foreground">&mdash;</span>
					{/if}
				</Table.Cell>
				<Table.Cell class="hidden md:table-cell text-xs text-muted-foreground text-right">
					{fmtSize(email.size_estimate)}
				</Table.Cell>
			</Table.Row>
		{/each}
		{#if emails.length === 0}
			<Table.Row>
				<Table.Cell colspan={6} class="text-center py-8 text-muted-foreground">
					No emails in this group.
				</Table.Cell>
			</Table.Row>
		{/if}
	</Table.Body>
</Table.Root>

{#if showPagination && onPageChange}
	<div class="flex items-center justify-center gap-4 py-2 border-t">
		<Button variant="outline" size="sm" disabled={page <= 1} onclick={() => onPageChange(page - 1)}>
			<ChevronLeft class="h-4 w-4" />
			Prev
		</Button>
		<span class="text-xs text-muted-foreground">
			Page {page} of {totalPages} ({total} emails)
		</span>
		<Button variant="outline" size="sm" disabled={page >= totalPages} onclick={() => onPageChange(page + 1)}>
			Next
			<ChevronRight class="h-4 w-4" />
		</Button>
	</div>
{/if}
