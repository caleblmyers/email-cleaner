<script lang="ts">
	import { Select as SelectPrimitive } from 'bits-ui';
	import type { Snippet } from 'svelte';

	interface Props {
		value?: string;
		onValueChange?: (value: string) => void;
		open?: boolean;
		onOpenChange?: (open: boolean) => void;
		disabled?: boolean;
		name?: string;
		required?: boolean;
		children?: Snippet;
		[key: string]: unknown;
	}

	let {
		value = $bindable(),
		onValueChange,
		open = $bindable(false),
		onOpenChange,
		disabled,
		name,
		required,
		children,
		...restProps
	}: Props = $props();
</script>

<SelectPrimitive.Root
	type="single"
	bind:value
	{onValueChange}
	bind:open
	{onOpenChange}
	{disabled}
	{name}
	{required}
	{...restProps}
>
	{#if children}
		{@render children()}
	{/if}
</SelectPrimitive.Root>
