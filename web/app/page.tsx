import Link from "next/link";
import { getPosts, CATEGORY_ORDER, SITE_NAME, SITE_DESC } from "@/lib/wp";
import PostCard from "@/components/PostCard";

export const revalidate = 600;

export default async function Home() {
  const posts = await getPosts(24);

  return (
    <div className="container">
      <section className="intro">
        <div className="avatar">Y</div>
        <div>
          <h1>{SITE_NAME}</h1>
          <p>{SITE_DESC}</p>
        </div>
      </section>

      <div className="chips">
        {CATEGORY_ORDER.map((c) => (
          <Link key={c.slug} href={`/category/${c.slug}`}>
            {c.name}
          </Link>
        ))}
      </div>

      {posts.length === 0 ? (
        <p className="empty">
          아직 발행된 글이 없습니다. 워드프레스에서 글을 공개하면 여기에 나타납니다.
        </p>
      ) : (
        <div className="feed">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
