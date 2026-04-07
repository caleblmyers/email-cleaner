<script lang="ts">
	import { Dialog as DialogPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils/cn.js';
	import type { Snippet } from 'svelte';

	interface Props {
		class?: string;
		level?: 1 | 2 | 3 | 4 | 5 | 6;
		children?: Snippet;
		[key: string]: unknown;
	}

	let { class: className, level = 3, children, ...restProps }: Props = $props();
</script>

<DialogPrimitive.Title
	{level}
	class={cn('text-lg font-semibold leading-none tracking-tight', className)}
	{...restProps}
>
	{#if children}
		{@render children()}
	{/if}
</DialogPrimitive.Title>
