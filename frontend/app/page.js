import fs from "fs";
import path from "path";

export default function Home() {
  const filePath = path.join(process.cwd(), "public", "index-veritas.html");
  const htmlContent = fs.readFileSync(filePath, "utf8");

  return <div dangerouslySetInnerHTML={{ __html: htmlContent }} />;
}
