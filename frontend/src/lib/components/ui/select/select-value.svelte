<script lang="ts">
	import { cn } from '$lib/utils/cn.js';

	interface Props {
		placeholder?: string;
		class?: string;
		value?: string;
	}

	let { placeholder = 'Select...', class: className, value }: Props = $props();
</script>

<span class={cn('pointer-events-none', className)}>
	{#if value}
		{value}
	{:else}
		<span class="text-muted-foreground">{placeholder}</span>
	{/if}
</span>
