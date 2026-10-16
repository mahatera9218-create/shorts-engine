import Link from "next/link";
import { getPosts, CATEGORY_ORDER } from "@/lib/wp";
import PostCard from "@/components/PostCard";

export const revalidate = 600;

export default async function Home() {
  const posts = await getPosts(24);

  return (
    <div className="container">
      <section className="intro">
        <div className="avatar">Y</div>
        <div>
          <h1>
            {process.env.NEXT_PUBLIC_INTRO_TITLE || "복잡한 돈, 쉽게 정리합니다"}
          </h1>
          <p>
            {process.env.NEXT_PUBLIC_INTRO_DESC ||
              "재테크·부동산·세금·연금을 공식 자료로 정확하게."}
          </p>
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
