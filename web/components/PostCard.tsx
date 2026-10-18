import Link from "next/link";
import {
  type WpPost,
  featuredImage,
  postCategory,
  stripHtml,
  formatDate,
} from "@/lib/wp";
import { stockPhoto } from "@/lib/photos";
import Thumb from "./Thumb";

// taihyoung 스타일: 썸네일 + (제목 → 카테고리·날짜 → 요약).
export default async function PostCard({ post, priority = false }: { post: WpPost; priority?: boolean }) {
  const cat = postCategory(post);
  const feat = featuredImage(post);
  const stock = await stockPhoto(cat?.slug, post.slug);
  const title = stripHtml(post.title.rendered);

  return (
    <Link href={`/${post.slug}`} className="post">
      <div className="thumb">
        <Thumb src={stock} fallback={feat?.url ?? null} alt={title} w={480} priority={priority} />
      </div>
      <div className="body">
        <h2 dangerouslySetInnerHTML={{ __html: post.title.rendered }} />
        <div className="meta">
          {cat ? <span className="cat">{cat.name}</span> : null}
          {formatDate(post.date)}
        </div>
        <p className="excerpt">{stripHtml(post.excerpt.rendered).slice(0, 120)}</p>
      </div>
    </Link>
  );
}
