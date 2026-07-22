import Link from "next/link";

export default function NotFound() {
  return (
    <>
      <h1>404</h1>
      <p>Страницата или наборът не е намерен. / Page or dataset not found.</p>
      <p>
        <Link href="/bg">Начало</Link> · <Link href="/en">Home</Link>
      </p>
    </>
  );
}
