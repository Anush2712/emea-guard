import { Link } from "react-router-dom";

export function Mark() {
  return <Link to="/" className="mark"><img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" />EMEA Guard</Link>;
}
