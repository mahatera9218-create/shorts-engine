import { getPosts, SITE_NAME, SITE_DESC } from "@/lib/wp";
import PostCard from "@/components/PostCard";

export const revalidate = 600;

export default async function Home() {
  const posts = await getPosts(24);

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
        <div className="post-grid">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
