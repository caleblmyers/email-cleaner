<script lang="ts">
	import { Select as SelectPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils/cn.js';
	import Check from 'lucide-svelte/icons/check';

	interface Props {
		value: string;
		label?: string;
		disabled?: boolean;
		class?: string;
		[key: string]: unknown;
	}

	let { value, label, disabled, class: className, ...restProps }: Props = $props();
</script>

<SelectPrimitive.Item
	{value}
	{label}
	{disabled}
	class={cn(
		'relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-2 pr-8 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
		className
	)}
	{...restProps}
>
	{#snippet children({ selected })}
		<span class="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
			{#if selected}
				<Check class="h-4 w-4" />
			{/if}
		</span>
		<span>{label ?? value}</span>
	{/snippet}
</SelectPrimitive.Item>
