export default function LongformTranscript({ transcript, suggestions }) {
  return <div className="max-h-48 overflow-auto text-sm my-3" aria-label="Transcript with selected source ranges highlighted">
    {transcript.segments.map((segment, index) => <p key={index} className="mb-2">
      <strong>{Math.floor(segment.start / 60)}:{String(Math.floor(segment.start % 60)).padStart(2, '0')} </strong>
      {segment.words.map(word => {
        const selected = suggestions.some(s => (!s.segment_id || s.segment_id === word.segment_id)
          && word.source_start_ms < s.end_ms && word.source_end_ms > s.start_ms);
        return selected
          ? <mark key={`${word.segment_id}:${word.word_id}`} className="bg-amber-200 text-black">{word.word}</mark>
          : <span key={`${word.segment_id}:${word.word_id}`}>{word.word}</span>;
      })}
    </p>)}
  </div>;
}
