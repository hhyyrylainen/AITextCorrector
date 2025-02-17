export const metadata = {
  title: "404 - Page Not Found",
  description: "The page you are looking for does not exist.",
};

export default function CreateNew() {
    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
                <ul className="list-inside list-disc text-sm text-left">
                    <h1><b>404</b> - Not Found</h1>
                </ul>
            </main>
        </div>
    );
}
