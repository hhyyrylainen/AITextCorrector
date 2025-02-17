export default function Home() {
    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
                <ul className="list-inside list-disc text-sm text-left">
                    <li>List of parts goes here</li>
                    <li>And second part</li>
                    <li>And if a really long item appears here then what happens to all of the stuff??? Will this eventually wrap around at some point?</li>
                </ul>
            </main>
        </div>
    );
}
