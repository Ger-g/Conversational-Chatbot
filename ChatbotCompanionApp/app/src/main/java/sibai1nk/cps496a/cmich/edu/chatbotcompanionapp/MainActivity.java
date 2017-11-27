package sibai1nk.cps496a.cmich.edu.chatbotcompanionapp;

import android.os.Bundle;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.DividerItemDecoration;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.view.View;
import android.widget.TextView;

import com.firebase.ui.database.FirebaseRecyclerAdapter;
import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;

public class MainActivity extends AppCompatActivity {
    private RecyclerView recyclerView;
    private DatabaseReference myref;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayoutManager llm = new LinearLayoutManager(this);
        llm.setReverseLayout(true);
        llm.setStackFromEnd(true);
        setContentView(R.layout.activity_main);
        recyclerView = (RecyclerView) findViewById(R.id.recyclerview);
        recyclerView.setHasFixedSize(true);
        recyclerView.setLayoutManager(llm);

        myref = FirebaseDatabase.getInstance().getReference().child("/messages");
        FirebaseRecyclerAdapter<Response, ResponseViewHolder> recyclerAdapter = new FirebaseRecyclerAdapter<Response, ResponseViewHolder>(
                Response.class,
                R.layout.individual_row,
                ResponseViewHolder.class,
                myref
        ) {
            @Override
            protected void populateViewHolder(ResponseViewHolder viewHolder, Response model, int position) {
                viewHolder.setContent(model.getMessage());

            }
        };
        DividerItemDecoration dividerItemDecoration = new DividerItemDecoration(recyclerView.getContext(),
                llm.getOrientation());
        dividerItemDecoration.setDrawable(getResources().getDrawable(R.drawable.divider));
        recyclerView.addItemDecoration(dividerItemDecoration);
        recyclerView.setAdapter(recyclerAdapter);
    }

    public static class ResponseViewHolder extends RecyclerView.ViewHolder {
        View mView;
        TextView textView_content;

        public ResponseViewHolder(View itemView) {
            super(itemView);
            mView = itemView;
            textView_content = itemView.findViewById(R.id.message);
        }


        public void setContent(String message) {
            System.out.println(message);
            textView_content.setText(message);
        }
    }
}

