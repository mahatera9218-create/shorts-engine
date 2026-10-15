import Link from "next/link";
import { getPosts, stripHtml, formatDate, SITE_NAME, SITE_DESC } from "@/lib/wp";

export const revalidate = 600;

export default async function Home() {
  const posts = await getPosts(20);

  return (
    <div className="container">
      <section className="hero">
        <h1>{SITE_NAME}</h1>
        <p>{SITE_DESC}</p>
      </section>

      {posts.length === 0 ? (
        <p style={{ color: "var(--muted)", padding: "40px 0 80px" }}>
          아직 발행된 글이 없습니다. 워드프레스에서 글을 공개하면 여기에
          나타납니다.
        </p>
      ) : (
        <ul className="post-list">
          {posts.map((post) => (
            <li key={post.id}>
              <Link href={`/${post.slug}`} className="post-card">
                <div className="post-card-meta">{formatDate(post.date)}</div>
                <h2
                  className="post-card-title"
                  dangerouslySetInnerHTML={{ __html: post.title.rendered }}
                />
                <p className="post-card-excerpt">
                  {stripHtml(post.excerpt.rendered).slice(0, 120)}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
