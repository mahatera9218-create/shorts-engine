import Link from "next/link";
import {
  type WpPost,
  featuredImage,
  postCategory,
  stripHtml,
  formatDate,
} from "@/lib/wp";

// 썸네일 + 카테고리 + 제목 + 날짜 + 요약 카드. 홈·카테고리·관련 글 공용.
export default function PostCard({ post }: { post: WpPost }) {
  const img = featuredImage(post);
  const cat = postCategory(post);
  return (
    <Link href={`/${post.slug}`} className="post-card">
      <div className="post-card-thumb">
        {img ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={img.url} alt={img.alt} loading="lazy" />
        ) : (
          <div className="post-card-thumb-fallback">억선생의 경제판</div>
        )}
      </div>
      <div className="post-card-body">
        {cat ? <span className="post-card-cat">{cat.name}</span> : null}
        <h2
          className="post-card-title"
          dangerouslySetInnerHTML={{ __html: post.title.rendered }}
        />
        <p className="post-card-excerpt">
          {stripHtml(post.excerpt.rendered).slice(0, 90)}
        </p>
        <div className="post-card-meta">{formatDate(post.date)}</div>
      </div>
    </Link>
  );
}
