<script lang="ts">
	import { Checkbox as CheckboxPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils/cn.js';
	import Check from 'lucide-svelte/icons/check';
	import Minus from 'lucide-svelte/icons/minus';

	interface Props {
		checked?: boolean;
		onCheckedChange?: (checked: boolean) => void;
		disabled?: boolean;
		required?: boolean;
		name?: string;
		value?: string;
		indeterminate?: boolean;
		class?: string;
		[key: string]: unknown;
	}

	let {
		checked = $bindable(false),
		onCheckedChange,
		disabled,
		required,
		name,
		value,
		indeterminate = false,
		class: className,
		...restProps
	}: Props = $props();
</script>

<CheckboxPrimitive.Root
	bind:checked
	{onCheckedChange}
	{disabled}
	{required}
	{name}
	{value}
	{indeterminate}
	class={cn(
		'peer h-4 w-4 shrink-0 rounded-sm border border-primary shadow focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
		className
	)}
	{...restProps}
>
	{#snippet children({ checked, indeterminate })}
		<div class="flex items-center justify-center text-current">
			{#if indeterminate}
				<Minus class="h-3.5 w-3.5" />
			{:else if checked}
				<Check class="h-3.5 w-3.5" />
			{/if}
		</div>
	{/snippet}
</CheckboxPrimitive.Root>
