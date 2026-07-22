interface PromptSuggestionsProps {
  label: string
  append: (message: { role: 'user'; content: string }) => void
  suggestions: string[]
}

export function PromptSuggestions({
  label,
  append,
  suggestions,
}: PromptSuggestionsProps) {
  return (
    <div className='space-y-6'>
      <h2 className='text-center text-2xl font-bold'>{label}</h2>
      <div className='grid gap-3 text-sm sm:grid-cols-3 sm:gap-4'>
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type='button'
            onClick={() => append({ role: 'user', content: suggestion })}
            className='h-max rounded-xl border bg-background p-4 text-left hover:bg-muted'
          >
            <p>{suggestion}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
